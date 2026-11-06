from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import SCHOOL_ROLES
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.payments.models import PlatformPayment
from apps.subscriptions.models import Subscription, SubscriptionStatus
from apps.subscriptions.state import effective_state_expression, expiring_filter
from apps.tenants.models import School, SchoolStatus

from .config import PlatformConfig
from .selectors import annotated_schools
from .serializers import PaymentSerializer, PlatformSchoolListSerializer

WINDOW_DAYS = 30


def _money(value) -> str:
    return f"{(value or Decimal('0')):.2f}"


def build_platform_dashboard() -> dict:
    """Real aggregates only. Student and teacher metrics are added with Phases 5-6."""
    now, cfg = timezone.now(), PlatformConfig.load()
    by_status = dict.fromkeys(SchoolStatus.values, 0)
    for row in School.objects.order_by().values("status").annotate(count=Count("id")):
        by_status[row["status"]] = row["count"]

    by_role = dict.fromkeys(SCHOOL_ROLES, 0)
    for row in User.objects.filter(school__isnull=False).order_by().values("role").annotate(count=Count("id")):
        by_role[row["role"]] = row["count"]

    today = now.date()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    per_day = {
        row["day"]: row["count"]
        for row in School.objects.filter(created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .order_by("day")
        .values("day")
        .annotate(count=Count("id"))
    }
    daily = [
        {"date": (start + timedelta(days=i)).isoformat(), "count": per_day.get(start + timedelta(days=i), 0)}
        for i in range(WINDOW_DAYS)
    ]

    sub_states = dict.fromkeys(SubscriptionStatus.values, 0)
    for row in (
        Subscription.objects.annotate(state=effective_state_expression(now, cfg.past_due_grace_days))
        .order_by().values("state").annotate(count=Count("id"))
    ):
        sub_states[row["state"]] = row["count"]

    revenue = [
        {"currency": row["currency"], "last_30_days": _money(row["recent"]), "all_time": _money(row["total"])}
        for row in PlatformPayment.objects.order_by().values("currency").annotate(
            total=Sum("amount"), recent=Sum("amount", filter=Q(payment_date__gte=start))
        ).order_by("currency")
    ]

    context = {"now": now, "cfg": cfg}
    recent_schools = annotated_schools(now, cfg).order_by("-created_at")[:5]
    recent_payments = PlatformPayment.objects.select_related("school", "created_by").order_by("-created_at")[:5]
    from apps.students.models import Student
    from apps.teachers.models import Teacher

    return {
        "people": {"students": Student.objects.count(), "teachers": Teacher.objects.count()},
        "schools": {"total": sum(by_status.values()), "by_status": by_status},
        "users": {"total": sum(by_role.values()), "by_role": by_role},
        "subscriptions": {"by_state": sub_states, "expiring_soon": Subscription.objects.filter(expiring_filter(now, cfg)).count()},
        "revenue": revenue,
        "registrations": {"last_30_days": sum(item["count"] for item in daily), "daily": daily},
        "recent_schools": PlatformSchoolListSerializer(recent_schools, many=True, context=context).data,
        "recent_payments": PaymentSerializer(recent_payments, many=True).data,
    }


@transaction.atomic
def create_plan(*, serializer, actor, request):
    plan = serializer.save()
    AuditService.record(
        AuditAction.PLAN_CREATED, actor=actor, entity_type="plan", entity_id=plan.id,
        description=f"Created plan {plan.name}", metadata={"slug": plan.slug}, request=request,
    )
    return plan


@transaction.atomic
def update_plan(*, serializer, actor, request):
    changed = sorted(serializer.validated_data.keys())
    plan = serializer.save()
    AuditService.record(
        AuditAction.PLAN_UPDATED, actor=actor, entity_type="plan", entity_id=plan.id,
        description=f"Updated plan {plan.name}", metadata={"fields": changed}, request=request,
    )
    return plan
