"""Request-time enforcement of subscription state (called from core.permissions.TenantAccess)."""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.core.exceptions import SubscriptionBlocked, SubscriptionExpired
from apps.platform_admin.config import PlatformConfig

from .state import BLOCKED, FULL, READ_ONLY, SAFE_METHODS, effective_state, has_full_access_quick

logger = logging.getLogger(__name__)


def enforce_subscription_access(school, method: str) -> None:
    """FULL: allowed. READ_ONLY (expired): safe methods only, writes get 402. BLOCKED: everything gets 403.
    A school with no subscription row should not exist (registration and the backfill create one) and fails closed."""
    try:
        sub = school.subscription
    except ObjectDoesNotExist:
        logger.error("School %s has no subscription; denying writes.", school.id)
        if method not in SAFE_METHODS:
            raise SubscriptionExpired() from None
        return

    now = timezone.now()
    if has_full_access_quick(sub, now):  # common case: no settings query
        return
    access = effective_state(sub, now, PlatformConfig.load()).access
    if access == FULL:
        return
    if access == READ_ONLY:
        if method in SAFE_METHODS:
            return
        raise SubscriptionExpired()
    if access == BLOCKED:
        raise SubscriptionBlocked()
