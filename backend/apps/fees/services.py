import uuid
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academics.models import Enrollment, EnrollmentStatus
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict
from apps.core.numbering import format_number, next_number, reserve_numbers

from .models import (
    Discount, DiscountKind, FeePayment, Fine, InvoiceItem, InvoiceStatus, PaymentStatus, StudentInvoice,
)

MAX_INVOICES_PER_RUN = 1000
ZERO = Decimal("0.00")


def _q(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def recalculate(invoice: StudentInvoice) -> StudentInvoice:
    """Single source of truth for an invoice's money fields; always derived from its rows."""
    agg = lambda qs: qs.aggregate(t=Sum("amount"))["t"] or ZERO
    invoice.subtotal = agg(invoice.items)
    invoice.discount_total = agg(invoice.discounts)
    invoice.fine_total = agg(invoice.fines)
    invoice.total = invoice.subtotal - invoice.discount_total + invoice.fine_total
    invoice.paid_total = agg(invoice.payments.filter(status=PaymentStatus.POSTED))
    invoice.balance = invoice.total - invoice.paid_total
    if invoice.balance < 0:
        raise ValidationError({"detail": ["This change would make the invoice total lower than what was already paid."]})
    if invoice.status != InvoiceStatus.VOID:
        if invoice.paid_total > 0 and invoice.balance == 0:
            invoice.status = InvoiceStatus.PAID
        elif invoice.paid_total > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        else:
            invoice.status = InvoiceStatus.ISSUED
    invoice.save(update_fields=["subtotal", "discount_total", "fine_total", "total", "paid_total", "balance", "status", "updated_at"])
    return invoice


def _locked(invoice_id) -> StudentInvoice:
    return StudentInvoice.objects.select_for_update().select_related("student", "school").get(pk=invoice_id)


class FeeService:
    @staticmethod
    @transaction.atomic
    def generate_invoices(*, school, structure, period_label, issue_date, due_date, section=None, actor, request) -> dict:
        items = list(structure.items.select_related("category"))
        if not items:
            raise ValidationError({"structure": ["This fee structure has no fee items."]})
        enrollments = Enrollment.objects.filter(school=school, session=structure.session, status=EnrollmentStatus.ENROLLED).select_related("student")
        if structure.school_class_id:
            enrollments = enrollments.filter(school_class_id=structure.school_class_id)
        if section is not None:
            enrollments = enrollments.filter(section=section)
        already = set(
            StudentInvoice.objects.filter(school=school, session=structure.session, period_label=period_label).exclude(status=InvoiceStatus.VOID).values_list("student_id", flat=True)
        )
        targets = [e for e in enrollments if e.student_id not in already]
        if len(targets) > MAX_INVOICES_PER_RUN:
            raise ValidationError({"detail": [f"Too many students at once ({len(targets)}). Generate per section (max {MAX_INVOICES_PER_RUN})."]})
        if not targets:
            return {"created": 0, "skipped": len(already)}

        prefix = school.settings.invoice_prefix
        start = reserve_numbers(school, "INVOICE", len(targets))
        subtotal = sum((i.amount for i in items), ZERO)
        invoices, rows = [], []
        for offset, enrollment in enumerate(targets):
            invoice_id = uuid.uuid4()
            invoices.append(StudentInvoice(
                id=invoice_id, school=school, invoice_number=format_number(prefix, start + offset), student_id=enrollment.student_id,
                enrollment=enrollment, session=structure.session, period_label=period_label, issue_date=issue_date, due_date=due_date,
                subtotal=subtotal, total=subtotal, balance=subtotal,
            ))
            rows.extend(
                InvoiceItem(school=school, invoice_id=invoice_id, category=i.category, description=i.category.name, quantity=1, unit_amount=i.amount, amount=i.amount)
                for i in items
            )
        StudentInvoice.objects.bulk_create(invoices)
        InvoiceItem.objects.bulk_create(rows)
        AuditService.record(
            AuditAction.INVOICES_GENERATED, actor=actor, school=school, entity_type="fee_structure", entity_id=structure.id,
            description=f"Generated {len(invoices)} invoice(s) for {period_label} from {structure.name}",
            metadata={"created": len(invoices), "skipped": len(already)}, request=request,
        )
        return {"created": len(invoices), "skipped": len(already)}

    @staticmethod
    @transaction.atomic
    def add_discount(*, invoice_id, kind, value, reason, actor) -> StudentInvoice:
        invoice = _locked(invoice_id)
        if invoice.status == InvoiceStatus.VOID:
            raise Conflict("A void invoice cannot be changed.", code="invalid_transition")
        value = _q(value)
        if kind == DiscountKind.PERCENT:
            if not (0 < value <= 100):
                raise ValidationError({"value": ["A percentage must be above 0 and at most 100."]})
            amount = _q(invoice.subtotal * value / 100)
        else:
            if value <= 0:
                raise ValidationError({"value": ["The discount must be above zero."]})
            amount = value
        Discount.objects.create(school=invoice.school, invoice=invoice, kind=kind, value=value, amount=amount, reason=reason, approved_by=actor)
        return recalculate(invoice)

    @staticmethod
    @transaction.atomic
    def add_fine(*, invoice_id, amount, reason, actor) -> StudentInvoice:
        invoice = _locked(invoice_id)
        if invoice.status == InvoiceStatus.VOID:
            raise Conflict("A void invoice cannot be changed.", code="invalid_transition")
        Fine.objects.create(school=invoice.school, invoice=invoice, amount=_q(amount), reason=reason, applied_on=date.today(), applied_by=actor)
        return recalculate(invoice)

    @staticmethod
    @transaction.atomic
    def void_invoice(*, invoice_id, reason, actor, request) -> StudentInvoice:
        invoice = _locked(invoice_id)
        if invoice.status == InvoiceStatus.VOID:
            raise Conflict("This invoice is already void.", code="invalid_transition")
        if invoice.payments.filter(status=PaymentStatus.POSTED).exists():
            raise Conflict("Reverse the payments first; an invoice with posted payments cannot be voided.", code="has_payments")
        invoice.status, invoice.void_reason = InvoiceStatus.VOID, reason
        invoice.save(update_fields=["status", "void_reason", "updated_at"])
        AuditService.record(
            AuditAction.INVOICE_VOIDED, actor=actor, school=invoice.school, entity_type="invoice", entity_id=invoice.id,
            description=f"Voided invoice {invoice.invoice_number}: {reason}", request=request,
        )
        return invoice

    @staticmethod
    @transaction.atomic
    def record_payment(*, invoice_id, amount, method, reference, paid_on, actor, request) -> FeePayment:
        invoice = _locked(invoice_id)
        if invoice.status == InvoiceStatus.VOID:
            raise Conflict("Payments cannot be recorded against a void invoice.", code="invalid_transition")
        amount = _q(amount)
        if amount <= 0:
            raise ValidationError({"amount": ["The amount must be above zero."]})
        if amount > invoice.balance:
            raise ValidationError({"amount": [f"The amount exceeds the outstanding balance ({invoice.balance})."]})
        if paid_on > date.today():
            raise ValidationError({"paid_on": ["The payment date cannot be in the future."]})
        number = format_number(invoice.school.settings.receipt_prefix, next_number(invoice.school, "RECEIPT"))
        payment = FeePayment.objects.create(
            school=invoice.school, invoice=invoice, receipt_number=number, amount=amount, method=method,
            reference=reference, paid_on=paid_on, received_by=actor,
        )
        recalculate(invoice)
        AuditService.record(
            AuditAction.FEE_PAYMENT_RECORDED, actor=actor, school=invoice.school, entity_type="fee_payment", entity_id=payment.id,
            description=f"Receipt {number}: {amount} for invoice {invoice.invoice_number}", request=request,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def reverse_payment(*, payment_id, reason, actor, request) -> FeePayment:
        payment = FeePayment.objects.select_for_update().select_related("invoice").get(pk=payment_id)
        if payment.status == PaymentStatus.REVERSED:
            raise Conflict("This payment was already reversed.", code="invalid_transition")
        if actor.role == Role.ACCOUNTANT and not (payment.received_by_id == actor.id and payment.created_at.date() == timezone.now().date()):
            raise PermissionDenied("Accountants can only reverse their own payments on the day they were recorded.")
        invoice = _locked(payment.invoice_id)
        payment.status, payment.reversed_at, payment.reversed_by, payment.reversal_reason = PaymentStatus.REVERSED, timezone.now(), actor, reason
        payment.save(update_fields=["status", "reversed_at", "reversed_by", "reversal_reason", "updated_at"])
        recalculate(invoice)
        AuditService.record(
            AuditAction.FEE_PAYMENT_REVERSED, actor=actor, school=payment.school, entity_type="fee_payment", entity_id=payment.id,
            description=f"Reversed receipt {payment.receipt_number}: {reason}", request=request,
        )
        return payment
