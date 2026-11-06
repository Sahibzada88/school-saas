from datetime import date, timedelta

from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.notifications.models import NotificationType, Severity
from apps.notifications.services import NotificationService
from apps.students.scope import guardian_users_by_student

from .models import InvoiceStatus, StudentInvoice

MAX_REMINDER_INVOICES = 1000


class FeeReminderService:
    @staticmethod
    def send(*, school, mode: str, days: int, actor, request) -> dict:
        """Remind parents (who have a sign-in account) about unpaid invoices: in-app notification + email when
        configured. Idempotent per invoice per day. WhatsApp/SMS are NOT sent by the system (use the WhatsApp links)."""
        today = date.today()
        queryset = StudentInvoice.objects.filter(
            school=school, status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID], balance__gt=0
        ).select_related("student")
        if mode == "overdue":
            queryset = queryset.filter(due_date__lt=today)
        elif mode == "due_soon":
            queryset = queryset.filter(due_date__gte=today, due_date__lte=today + timedelta(days=days))
        else:
            raise ValidationError({"mode": ["Use 'overdue' or 'due_soon'."]})
        invoices = list(queryset.order_by("due_date")[: MAX_REMINDER_INVOICES + 1])
        if len(invoices) > MAX_REMINDER_INVOICES:
            raise ValidationError({"detail": [f"More than {MAX_REMINDER_INVOICES} invoices match. Narrow it down (use 'due_soon' with fewer days)."]})

        users_by_student = guardian_users_by_student(school, {i.student_id for i in invoices})
        notified = no_account = 0
        for invoice in invoices:
            users = users_by_student.get(invoice.student_id, [])
            if not users:
                no_account += 1
                continue
            notified += NotificationService.notify_users(
                school, users, type=NotificationType.FEE_REMINDER, title=f"Fee reminder: {invoice.student.first_name}",
                body=f"Invoice {invoice.invoice_number}: balance {invoice.balance} due {invoice.due_date:%d %b %Y}.",
                severity=Severity.WARNING, data={"invoice": str(invoice.id)}, dedupe_key=f"FEE_REMINDER:{invoice.id}:{today.isoformat()}",
                email_template="fee_reminder",
                email_context={"student": invoice.student.full_name, "invoice": invoice.invoice_number, "amount": str(invoice.balance), "due": f"{invoice.due_date:%d %b %Y}"},
            )
        result = {"invoices": len(invoices), "notified": notified, "no_account": no_account}
        AuditService.record(
            AuditAction.FEE_REMINDERS_SENT, actor=actor, school=school, entity_type="fee_reminders", entity_id=mode,
            description=f"Fee reminders ({mode}): {result}", metadata=result, request=request,
        )
        return result
