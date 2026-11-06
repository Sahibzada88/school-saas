"""DB-backed throttling (serverless instances share no memory).

Trade-off: per-email lockout lets an attacker temporarily lock a known victim out for the window.
That is accepted; the window is short and the per-IP limit stops bulk abuse.
"""
import random
from datetime import timedelta

from django.utils import timezone

from apps.core.exceptions import TooManyRequests

from ..models import AttemptScope, LoginAttempt

LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_MAX_FAILURES_PER_EMAIL = 5
LOGIN_MAX_FAILURES_PER_IP = 20
HOURLY_WINDOW = timedelta(hours=1)
REGISTER_MAX_PER_IP_PER_HOUR = 5
RESET_MAX_PER_IP_PER_HOUR = 10
RESET_MAX_PER_EMAIL_PER_HOUR = 3
RETENTION = timedelta(days=7)


def _prune() -> None:
    """Opportunistic cleanup (no scheduler available)."""
    if random.random() < 0.02:
        LoginAttempt.objects.filter(created_at__lt=timezone.now() - RETENTION).delete()


def record_attempt(scope: str, *, email_norm: str = "", ip: str | None = None, succeeded: bool = False) -> None:
    LoginAttempt.objects.create(scope=scope, email_norm=email_norm, ip=ip, succeeded=succeeded)
    _prune()


def check_login_allowed(email_norm: str, ip: str | None) -> None:
    since = timezone.now() - LOGIN_WINDOW
    attempts = LoginAttempt.objects.filter(scope=AttemptScope.LOGIN, created_at__gte=since)

    last_success = (
        attempts.filter(email_norm=email_norm, succeeded=True)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    email_failures = attempts.filter(
        email_norm=email_norm, succeeded=False, created_at__gt=last_success or since
    ).count()
    if email_failures >= LOGIN_MAX_FAILURES_PER_EMAIL:
        raise TooManyRequests("Too many failed sign-in attempts. Please try again in a few minutes.")

    if ip and attempts.filter(ip=ip, succeeded=False).count() >= LOGIN_MAX_FAILURES_PER_IP:
        raise TooManyRequests("Too many failed sign-in attempts. Please try again in a few minutes.")


def check_and_record_registration(ip: str | None) -> None:
    if ip:
        since = timezone.now() - HOURLY_WINDOW
        count = LoginAttempt.objects.filter(scope=AttemptScope.REGISTER, ip=ip, created_at__gte=since).count()
        if count >= REGISTER_MAX_PER_IP_PER_HOUR:
            raise TooManyRequests("Too many registration attempts. Please try again later.")
    record_attempt(AttemptScope.REGISTER, ip=ip)


def check_and_record_password_reset(email_norm: str, ip: str | None) -> bool:
    """Raises for IP abuse; returns False (caller silently sends nothing) when this email is over its limit,
    so the response never reveals whether the account exists."""
    since = timezone.now() - HOURLY_WINDOW
    attempts = LoginAttempt.objects.filter(scope=AttemptScope.PASSWORD_RESET, created_at__gte=since)
    if ip and attempts.filter(ip=ip).count() >= RESET_MAX_PER_IP_PER_HOUR:
        raise TooManyRequests("Too many password reset requests. Please try again later.")
    allowed = attempts.filter(email_norm=email_norm).count() < RESET_MAX_PER_EMAIL_PER_HOUR
    record_attempt(AttemptScope.PASSWORD_RESET, email_norm=email_norm, ip=ip)
    return allowed
