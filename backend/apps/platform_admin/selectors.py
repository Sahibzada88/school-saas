from datetime import datetime

from django.db.models import Case, Count, F, OuterRef, Q, Subquery, When

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.subscriptions.models import Subscription, SubscriptionStatus as S
from apps.subscriptions.state import effective_state_expression
from apps.tenants.models import School

from .config import PlatformConfig


def annotated_schools(now: datetime | None = None, cfg: PlatformConfig | None = None):
    """Schools with user counts, first School Admin email and the SQL-derived subscription state (no N+1)."""
    from django.utils import timezone

    now = now or timezone.now()
    cfg = cfg or PlatformConfig.load()
    first_admin_email = (
        User.objects.filter(school=OuterRef("pk"), role=Role.SCHOOL_ADMIN).order_by("created_at").values("email")[:1]
    )
    return School.objects.select_related("status_changed_by", "subscription__plan").annotate(
        user_count=Count("users", distinct=True),
        active_user_count=Count("users", filter=Q(users__is_active=True), distinct=True),
        admin_email=Subquery(first_admin_email),
        subscription_state=effective_state_expression(now, cfg.past_due_grace_days, prefix="subscription__"),
    )


def annotated_subscriptions(now: datetime, cfg: PlatformConfig):
    return Subscription.objects.select_related("school", "plan").annotate(
        effective=effective_state_expression(now, cfg.past_due_grace_days),
        ends_at=Case(When(status=S.TRIALING, then=F("trial_end")), default=F("end_date")),
    )
