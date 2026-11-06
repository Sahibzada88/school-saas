import calendar
import logging
from datetime import datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict
from apps.notifications.models import NotificationType, Severity
from apps.notifications.services import NotificationService
from apps.platform_admin.config import PlatformConfig

from .models import Plan, Subscription, SubscriptionEvent, SubscriptionEventType as E, SubscriptionStatus as S
from .state import EffectiveState, effective_state, summarize

logger = logging.getLogger(__name__)


def add_months(value: datetime, months: int) -> datetime:
    """Calendar-aware month addition (Jan 31 + 1 month = Feb 28/29)."""
    index = value.month - 1 + months
    year, month = value.year + index // 12, index % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def get_subscription(school) -> Subscription | None:
    try:
        return school.subscription
    except ObjectDoesNotExist:
        return None


class SubscriptionService:
    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _locked(subscription_id) -> Subscription:
        # of=("self",): the plan join is nullable, and Postgres cannot lock the nullable side of an outer join.
        return (
            Subscription.objects.select_for_update(of=("self",)).select_related("plan", "school").get(pk=subscription_id)
        )

    @staticmethod
    def record_event(sub: Subscription, event_type: str, *, actor=None, reason: str = "", **extra) -> SubscriptionEvent:
        return SubscriptionEvent.objects.create(
            subscription=sub, school=sub.school, event_type=event_type, actor=actor, reason=reason, **extra
        )

    # ------------------------------------------------------------------ trial
    @staticmethod
    def start_trial(school, *, actor=None) -> Subscription:
        """Called inside the registration transaction. Duration and plan are platform settings, never constants."""
        cfg = PlatformConfig.load()
        plan = Plan.objects.filter(slug=cfg.trial_plan_slug, is_active=True).first() if cfg.trial_plan_slug else None
        now = timezone.now()
        sub = Subscription.objects.create(
            school=school, plan=plan, status=S.TRIALING, trial_start=now,
            trial_end=now + timedelta(days=cfg.trial_duration_days),
        )
        SubscriptionService.record_event(
            sub, E.TRIAL_STARTED, actor=actor, to_status=S.TRIALING, to_plan=plan, delta_days=cfg.trial_duration_days
        )
        NotificationService.notify_school_admins(
            school, type=NotificationType.TRIAL_STARTED, title="Your free trial has started",
            body=f"You have {cfg.trial_duration_days} days to explore every feature.",
            dedupe_key=f"TRIAL_STARTED:{sub.id}",
        )
        return sub

    # ------------------------------------------------------------------ lazy synchronisation
    @staticmethod
    def sync(school) -> tuple[Subscription, EffectiveState] | None:
        """Persist time-driven transitions and create due notifications. Idempotent and race-safe, so it can run on any
        request (me, dashboard, notifications) instead of a scheduler."""
        sub = Subscription.objects.select_related("plan").filter(school=school).first()
        if sub is None:
            return None
        now, cfg = timezone.now(), PlatformConfig.load()
        eff = effective_state(sub, now, cfg)

        if eff.state in (S.PAST_DUE, S.EXPIRED) and sub.status != eff.state:
            updated = Subscription.objects.filter(pk=sub.pk, status=sub.status).update(status=eff.state, updated_at=now)
            if updated:  # only the request that wins the conditional UPDATE records the event
                SubscriptionService.record_event(
                    sub, E.STATE_CHANGED, from_status=sub.status, to_status=eff.state, metadata={"automatic": True}
                )
                sub.status = eff.state
        SubscriptionService._notify_due(school, sub, eff)
        return sub, eff

    @staticmethod
    def sync_quietly(school) -> tuple[Subscription, EffectiveState] | None:
        """sync() for read paths: a billing hiccup must never break sign-in or the dashboard."""
        try:
            return SubscriptionService.sync(school)
        except Exception:
            logger.exception("Subscription sync failed for school %s", getattr(school, "id", None))
            return None

    @staticmethod
    def _notify_due(school, sub: Subscription, eff: EffectiveState) -> None:
        notify = NotificationService.notify_school_admins
        never_paid = sub.start_date is None
        if eff.state == S.TRIALING and eff.is_expiring:
            notify(
                school, type=NotificationType.TRIAL_EXPIRING, severity=Severity.WARNING,
                title="Your free trial is ending soon",
                body=f"{eff.days_remaining} day(s) left. Contact platform administration to subscribe.",
                dedupe_key=f"TRIAL_EXPIRING:{sub.id}:{sub.trial_end.date().isoformat()}",
                email_template="trial_expiring", email_context={"days": eff.days_remaining},
            )
        elif eff.state == S.EXPIRED and never_paid:
            notify(
                school, type=NotificationType.TRIAL_EXPIRED, severity=Severity.CRITICAL,
                title="Your free trial has ended",
                body="Your data is safe. Contact platform administration to subscribe.",
                dedupe_key=f"TRIAL_EXPIRED:{sub.id}:{sub.trial_end.date().isoformat()}",
                email_template="trial_expired", email_context={},
            )
        elif eff.state == S.ACTIVE and eff.is_expiring and sub.end_date:
            notify(
                school, type=NotificationType.SUBSCRIPTION_EXPIRING, severity=Severity.WARNING,
                title="Your subscription is expiring soon",
                body=f"{eff.days_remaining} day(s) left. Contact platform administration to renew.",
                dedupe_key=f"SUBSCRIPTION_EXPIRING:{sub.id}:{sub.end_date.date().isoformat()}",
                email_template="subscription_expiring", email_context={"days": eff.days_remaining},
            )
        elif eff.state in (S.PAST_DUE, S.EXPIRED) and not never_paid and sub.end_date:
            notify(
                school, type=NotificationType.SUBSCRIPTION_EXPIRED, severity=Severity.CRITICAL,
                title="Your subscription has expired",
                body="Please renew to keep full access. Your data is safe.",
                dedupe_key=f"SUBSCRIPTION_EXPIRED:{sub.id}:{sub.end_date.date().isoformat()}",
                email_template="subscription_expired", email_context={},
            )

    @staticmethod
    def summary(school) -> dict | None:
        result = SubscriptionService.sync_quietly(school)
        if result is None:
            return None
        sub, eff = result
        return summarize(sub, eff)

    # ------------------------------------------------------------------ Super Admin operations
    @staticmethod
    def _audit(action: str, sub: Subscription, actor, request, description: str, **metadata) -> None:
        AuditService.record(
            action, actor=actor, school=sub.school, entity_type="subscription", entity_id=sub.id,
            description=description, metadata=metadata, request=request,
        )

    @staticmethod
    @transaction.atomic
    def extend_trial(*, subscription_id, days: int, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if sub.start_date is not None:
            raise Conflict("This school has a paid subscription; extend the subscription instead.", code="invalid_transition")
        if sub.status == S.SUSPENDED:
            raise Conflict("Resume the suspended subscription first.", code="invalid_transition")
        previous = sub.status
        sub.trial_end = max(sub.trial_end, timezone.now()) + timedelta(days=days)
        sub.status = S.TRIALING
        sub.save(update_fields=["trial_end", "status", "updated_at"])
        SubscriptionService.record_event(
            sub, E.TRIAL_EXTENDED, actor=actor, reason=reason, from_status=previous, to_status=S.TRIALING, delta_days=days
        )
        SubscriptionService._audit(
            AuditAction.SUBSCRIPTION_TRIAL_EXTENDED, sub, actor, request, f"Trial extended by {days} day(s): {reason}", days=days
        )
        NotificationService.notify_school_admins(
            sub.school, type=NotificationType.SUBSCRIPTION_EXTENDED, title="Your free trial was extended",
            body=f"Your trial now ends on {sub.trial_end:%d %b %Y}.",
        )
        return sub

    @staticmethod
    @transaction.atomic
    def extend_subscription(*, subscription_id, days: int, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if sub.start_date is None or sub.end_date is None:
            raise Conflict("This school has never paid; extend its trial instead.", code="invalid_transition")
        if sub.status == S.SUSPENDED:
            raise Conflict("Resume the suspended subscription first.", code="invalid_transition")
        previous = sub.status
        sub.end_date = max(sub.end_date, timezone.now()) + timedelta(days=days)
        sub.status, sub.cancelled_at = S.ACTIVE, None
        sub.save(update_fields=["end_date", "status", "cancelled_at", "updated_at"])
        SubscriptionService.record_event(
            sub, E.EXTENDED, actor=actor, reason=reason, from_status=previous, to_status=S.ACTIVE, delta_days=days
        )
        SubscriptionService._audit(
            AuditAction.SUBSCRIPTION_EXTENDED, sub, actor, request, f"Subscription extended by {days} day(s): {reason}", days=days
        )
        NotificationService.notify_school_admins(
            sub.school, type=NotificationType.SUBSCRIPTION_EXTENDED, title="Your subscription was extended",
            body=f"Your subscription now runs until {sub.end_date:%d %b %Y}.",
        )
        return sub

    @staticmethod
    @transaction.atomic
    def change_plan(*, subscription_id, plan: Plan, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if not plan.is_active:
            raise ValidationError({"plan": ["This plan is inactive and cannot be assigned."]})
        if sub.plan_id == plan.id:
            raise Conflict("The school is already on this plan.", code="invalid_transition")
        previous = sub.plan
        sub.plan = plan
        sub.save(update_fields=["plan", "updated_at"])
        SubscriptionService.record_event(sub, E.PLAN_CHANGED, actor=actor, reason=reason, from_plan=previous, to_plan=plan)
        SubscriptionService._audit(
            AuditAction.SUBSCRIPTION_PLAN_CHANGED, sub, actor, request,
            f"Plan changed from {previous.name if previous else 'none'} to {plan.name}", to=plan.slug,
        )
        return sub

    @staticmethod
    @transaction.atomic
    def cancel(*, subscription_id, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if sub.status not in (S.ACTIVE, S.PAST_DUE):
            raise Conflict("Only an active or past-due subscription can be cancelled.", code="invalid_transition")
        previous = sub.status
        sub.status, sub.cancelled_at = S.CANCELLED, timezone.now()
        sub.save(update_fields=["status", "cancelled_at", "updated_at"])
        SubscriptionService.record_event(sub, E.CANCELLED, actor=actor, reason=reason, from_status=previous, to_status=S.CANCELLED)
        SubscriptionService._audit(AuditAction.SUBSCRIPTION_CANCELLED, sub, actor, request, f"Subscription cancelled: {reason}")
        return sub

    @staticmethod
    @transaction.atomic
    def suspend(*, subscription_id, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if sub.status == S.SUSPENDED:
            raise Conflict("The subscription is already suspended.", code="invalid_transition")
        previous = sub.status
        sub.status, sub.suspended_at = S.SUSPENDED, timezone.now()
        sub.save(update_fields=["status", "suspended_at", "updated_at"])
        SubscriptionService.record_event(sub, E.SUSPENDED, actor=actor, reason=reason, from_status=previous, to_status=S.SUSPENDED)
        SubscriptionService._audit(AuditAction.SUBSCRIPTION_SUSPENDED, sub, actor, request, f"Subscription suspended: {reason}")
        return sub

    @staticmethod
    @transaction.atomic
    def resume(*, subscription_id, actor, reason: str, request) -> Subscription:
        sub = SubscriptionService._locked(subscription_id)
        if sub.status != S.SUSPENDED:
            raise Conflict("The subscription is not suspended.", code="invalid_transition")
        # The restored status is only a starting point: effective_state() re-derives expiry from the timestamps.
        restored = S.ACTIVE if sub.start_date else S.TRIALING
        sub.status, sub.suspended_at = restored, None
        sub.save(update_fields=["status", "suspended_at", "updated_at"])
        SubscriptionService.record_event(sub, E.RESUMED, actor=actor, reason=reason, from_status=S.SUSPENDED, to_status=restored)
        SubscriptionService._audit(AuditAction.SUBSCRIPTION_RESUMED, sub, actor, request, "Subscription resumed")
        return sub
