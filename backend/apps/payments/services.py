from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import DomainError
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService
from apps.subscriptions.models import Plan, Subscription, SubscriptionEventType as E, SubscriptionStatus as S
from apps.subscriptions.services import SubscriptionService, add_months

from .models import PlatformPayment


class PaymentService:
    @staticmethod
    def record_payment(
        *, school, amount, currency: str, payment_method: str, transaction_reference: str, payment_date: date,
        months: int, notes: str, plan: Plan | None, actor, request,
    ) -> PlatformPayment:
        """Record a manual payment and extend the subscription, atomically.

        Renewal rule: new period starts at max(end_date, now) and lasts `months` calendar months. The first payment
        activates the subscription (any unused trial time is not carried over). A suspended subscription stays
        suspended; the payment only moves its end date."""
        try:
            with transaction.atomic():
                try:
                    sub = (
                        Subscription.objects.select_for_update(of=("self",)).select_related("plan", "school").get(school=school)
                    )
                except Subscription.DoesNotExist:
                    raise DomainError("This school has no subscription record.", code="no_subscription") from None

                now = timezone.now()
                if plan is not None and plan.id != sub.plan_id:
                    if not plan.is_active:
                        raise ValidationError({"plan": ["This plan is inactive and cannot be assigned."]})
                    previous_plan, sub.plan = sub.plan, plan
                    SubscriptionService.record_event(
                        sub, E.PLAN_CHANGED, actor=actor, reason="Changed while recording a payment",
                        from_plan=previous_plan, to_plan=plan,
                    )

                period_start = sub.end_date if (sub.end_date and sub.end_date > now) else now
                period_end = add_months(period_start, months)
                first_payment = sub.start_date is None
                previous_status = sub.status
                if first_payment:
                    sub.start_date = now
                sub.end_date, sub.cancelled_at = period_end, None
                if previous_status != S.SUSPENDED:
                    sub.status = S.ACTIVE
                sub.save(update_fields=["plan", "start_date", "end_date", "cancelled_at", "status", "updated_at"])

                payment = PlatformPayment.objects.create(
                    school=school, subscription=sub, amount=amount, currency=currency, payment_method=payment_method,
                    transaction_reference=transaction_reference, payment_date=payment_date, months=months,
                    period_start=period_start, period_end=period_end, notes=notes, created_by=actor,
                )
                SubscriptionService.record_event(
                    sub, E.ACTIVATED if first_payment else E.RENEWED, actor=actor, from_status=previous_status,
                    to_status=sub.status, delta_days=(period_end - period_start).days,
                    metadata={"payment_id": str(payment.id), "months": months},
                )
                AuditService.record(
                    AuditAction.PAYMENT_RECORDED, actor=actor, school=school, entity_type="payment", entity_id=payment.id,
                    description=f"Recorded {currency} {amount} via {payment_method} for {months} month(s)",
                    metadata={"months": months, "reference": transaction_reference}, request=request,
                )
                if first_payment and sub.status == S.ACTIVE:
                    NotificationService.notify_school_admins(
                        school, type=NotificationType.SUBSCRIPTION_ACTIVATED, title="Your subscription is active",
                        body=f"Thank you. Your subscription runs until {period_end:%d %b %Y}.",
                        dedupe_key=f"SUBSCRIPTION_ACTIVATED:{sub.id}",
                    )
                NotificationService.notify_school_admins(
                    school, type=NotificationType.PAYMENT_RECEIVED, title="Payment received",
                    body=f"We received {currency} {amount}. Your subscription now runs until {period_end:%d %b %Y}.",
                    dedupe_key=f"PAYMENT_RECEIVED:{payment.id}",
                    email_template="payment_confirmation", email_context={"amount": f"{currency} {amount}", "until": f"{period_end:%d %b %Y}"},
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"transaction_reference": ["A payment with this method and reference was already recorded."]}
            ) from exc
        return payment
