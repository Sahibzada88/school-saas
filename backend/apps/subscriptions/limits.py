from apps.core.exceptions import PlanLimitReached

from .services import get_subscription

LIMIT_FIELDS = {"students": "max_students", "teachers": "max_teachers", "classes": "max_classes"}


def enforce_plan_limit(school, resource: str, current_count: int) -> None:
    """Raise 403 plan_limit_reached when creating one more `resource` would exceed the school's plan.
    No plan (or a NULL limit) means unlimited."""
    sub = get_subscription(school)
    plan = sub.plan if sub else None
    limit = getattr(plan, LIMIT_FIELDS[resource], None) if plan else None
    if limit is not None and current_count >= limit:
        raise PlanLimitReached(f"Your plan allows up to {limit} {resource}. Contact platform administration to upgrade.")
