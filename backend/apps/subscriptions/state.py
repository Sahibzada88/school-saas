"""Deterministic, timestamp-based subscription state.

`effective_state()` (Python) and `effective_state_expression()` (SQL CASE) implement ONE decision table; a test
asserts they agree row by row. Nothing here needs a scheduler: a trial or subscription "expires" the moment
`now` passes the relevant timestamp.

Decision table (first match wins), `status` = persisted/manual status:
  SUSPENDED                                  -> SUSPENDED   BLOCKED
  TRIALING   and now <  trial_end            -> TRIALING    FULL
  TRIALING                                   -> EXPIRED     per expired_access_mode
  ACTIVE|PAST_DUE and now < end_date         -> ACTIVE      FULL   (expiring = within N days of end_date)
  ACTIVE|PAST_DUE and now < end_date + grace -> PAST_DUE    FULL   (grace period, warning)
  CANCELLED  and now <  end_date             -> CANCELLED   FULL   (until the paid period ends)
  everything else (incl. missing end_date)   -> EXPIRED     per expired_access_mode
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Case, Q, Value, When

from .models import SubscriptionStatus as S

FULL = "FULL"
READ_ONLY = "READ_ONLY"
BLOCKED = "BLOCKED"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class EffectiveState:
    state: str
    access: str
    days_remaining: int | None
    is_expiring: bool
    ends_at: datetime | None
    in_grace: bool = False


def _days_until(target: datetime, now: datetime) -> int:
    return max(0, math.ceil((target - now).total_seconds() / 86400))


def effective_state(sub, now: datetime, cfg) -> EffectiveState:
    expired_access = BLOCKED if cfg.expired_access_mode == "BLOCKED" else READ_ONLY

    if sub.status == S.SUSPENDED:
        return EffectiveState(S.SUSPENDED, BLOCKED, None, False, None)

    if sub.status == S.TRIALING:
        if now < sub.trial_end:
            days = _days_until(sub.trial_end, now)
            return EffectiveState(S.TRIALING, FULL, days, days <= cfg.trial_expiring_notice_days, sub.trial_end)
        return EffectiveState(S.EXPIRED, expired_access, None, False, sub.trial_end)

    if sub.status in (S.ACTIVE, S.PAST_DUE):
        end = sub.end_date
        if end is None:
            return EffectiveState(S.EXPIRED, expired_access, None, False, None)
        if now < end:
            days = _days_until(end, now)
            return EffectiveState(S.ACTIVE, FULL, days, days <= cfg.expiring_notice_days, end)
        grace_end = end + timedelta(days=cfg.past_due_grace_days)
        if now < grace_end:
            return EffectiveState(S.PAST_DUE, FULL, _days_until(grace_end, now), False, grace_end, in_grace=True)
        return EffectiveState(S.EXPIRED, expired_access, None, False, grace_end)

    if sub.status == S.CANCELLED and sub.end_date and now < sub.end_date:
        return EffectiveState(S.CANCELLED, FULL, _days_until(sub.end_date, now), False, sub.end_date)

    return EffectiveState(S.EXPIRED, expired_access, None, False, sub.end_date)


def has_full_access_quick(sub, now: datetime) -> bool:
    """Request fast path: True when FULL access is certain without loading platform settings."""
    if sub.status == S.TRIALING:
        return now < sub.trial_end
    if sub.status in (S.ACTIVE, S.PAST_DUE):
        return sub.end_date is not None and now < sub.end_date
    return False


def effective_state_expression(now: datetime, grace_days: int, prefix: str = ""):
    """SQL twin of effective_state().state. `prefix` addresses the subscription through a relation
    (e.g. "subscription__" when annotating schools). Rows without a subscription yield "NONE"."""

    def q(**kwargs):
        return Q(**{f"{prefix}{key}": value for key, value in kwargs.items()})

    paid = [S.ACTIVE, S.PAST_DUE]
    return Case(
        When(q(status__isnull=True), then=Value("NONE")),
        When(q(status=S.SUSPENDED), then=Value(S.SUSPENDED)),
        When(q(status=S.TRIALING, trial_end__gt=now), then=Value(S.TRIALING)),
        When(q(status__in=paid, end_date__gt=now), then=Value(S.ACTIVE)),
        When(q(status__in=paid, end_date__gt=now - timedelta(days=grace_days)), then=Value(S.PAST_DUE)),
        When(q(status=S.CANCELLED, end_date__gt=now), then=Value(S.CANCELLED)),
        default=Value(S.EXPIRED),
    )


def expiring_filter(now: datetime, cfg, prefix: str = "") -> Q:
    """Rows that are FULL-access but within the notice window (SQL twin of EffectiveState.is_expiring)."""
    trial = Q(**{f"{prefix}status": S.TRIALING, f"{prefix}trial_end__gt": now,
                 f"{prefix}trial_end__lte": now + timedelta(days=cfg.trial_expiring_notice_days)})
    paid = Q(**{f"{prefix}status__in": [S.ACTIVE, S.PAST_DUE], f"{prefix}end_date__gt": now,
                f"{prefix}end_date__lte": now + timedelta(days=cfg.expiring_notice_days)})
    return trial | paid


def summarize(sub, eff: EffectiveState) -> dict:
    """Public, school-safe summary (used by /auth/me and the platform serializers)."""
    return {
        "state": eff.state,
        "access": eff.access,
        "days_remaining": eff.days_remaining,
        "is_expiring": eff.is_expiring,
        "in_grace": eff.in_grace,
        "ends_at": eff.ends_at,
        "is_trial": sub.start_date is None,
        "plan": {"name": sub.plan.name, "slug": sub.plan.slug} if sub.plan_id else None,
    }
