from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TenantModel, TenantSoftDeleteModel


class FeeCategory(TenantSoftDeleteModel):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=20)
    is_recurring = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "code"], condition=Q(is_deleted=False), name="uniq_fee_category_code_active")]


class Frequency(models.TextChoices):
    ONE_TIME = "ONE_TIME", "One time"
    MONTHLY = "MONTHLY", "Monthly"
    TERM = "TERM", "Per term"
    ANNUAL = "ANNUAL", "Annual"


class FeeStructure(TenantSoftDeleteModel):
    session = models.ForeignKey("academics.AcademicSession", on_delete=models.PROTECT, related_name="+")
    school_class = models.ForeignKey("academics.SchoolClass", null=True, blank=True, on_delete=models.PROTECT, related_name="+")  # NULL = all classes
    name = models.CharField(max_length=100)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)


class FeeStructureItem(TenantModel):
    structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["structure", "category"], name="uniq_structure_category"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="structure_item_amount_non_negative"),
        ]


class InvoiceStatus(models.TextChoices):
    ISSUED = "ISSUED", "Issued"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially paid"
    PAID = "PAID", "Paid"
    VOID = "VOID", "Void"


class StudentInvoice(TenantModel):
    invoice_number = models.CharField(max_length=30)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="invoices")
    enrollment = models.ForeignKey("academics.Enrollment", null=True, blank=True, on_delete=models.PROTECT, related_name="invoices")
    session = models.ForeignKey("academics.AcademicSession", on_delete=models.PROTECT, related_name="+")
    period_label = models.CharField(max_length=40)
    issue_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fine_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED)
    void_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "invoice_number"], name="uniq_invoice_number"),
            models.UniqueConstraint(fields=["student", "session", "period_label"], condition=~Q(status="VOID"), name="uniq_invoice_period"),
            models.CheckConstraint(condition=Q(balance=F("total") - F("paid_total")) & Q(balance__gte=0) & Q(paid_total__gte=0), name="invoice_balance_consistent"),
        ]
        indexes = [
            models.Index(fields=["school", "status", "due_date"], name="inv_school_status_due_idx"),
            models.Index(fields=["school", "student"], name="inv_school_student_idx"),
        ]


class InvoiceItem(TenantModel):
    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(FeeCategory, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=150)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)


class DiscountKind(models.TextChoices):
    PERCENT = "PERCENT", "Percent"
    FIXED = "FIXED", "Fixed"


class Discount(TenantModel):
    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name="discounts")
    kind = models.CharField(max_length=8, choices=DiscountKind.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=200)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")


class Fine(TenantModel):
    invoice = models.ForeignKey(StudentInvoice, on_delete=models.CASCADE, related_name="fines")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=200)
    applied_on = models.DateField()
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")


class FeeMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank"
    ONLINE = "ONLINE", "Online"
    CHEQUE = "CHEQUE", "Cheque"
    OTHER = "OTHER", "Other"


class PaymentStatus(models.TextChoices):
    POSTED = "POSTED", "Posted"
    REVERSED = "REVERSED", "Reversed"


class FeePayment(TenantModel):
    """Student fee payment. Completely separate from SaaS subscription payments (apps.payments)."""

    invoice = models.ForeignKey(StudentInvoice, on_delete=models.PROTECT, related_name="payments")
    receipt_number = models.CharField(max_length=30)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=8, choices=FeeMethod.choices)
    reference = models.CharField(max_length=100, blank=True)
    paid_on = models.DateField()
    status = models.CharField(max_length=8, choices=PaymentStatus.choices, default=PaymentStatus.POSTED)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reversal_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "receipt_number"], name="uniq_receipt_number"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="fee_payment_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["school", "paid_on"], name="feepay_school_paid_idx"),
            models.Index(fields=["invoice"], name="feepay_invoice_idx"),
        ]
