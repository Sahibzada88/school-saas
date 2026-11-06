import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.utils import get_client_ip

from ..models import PasswordResetToken, User
from . import throttling
from .auth import AuthService

logger = logging.getLogger(__name__)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def send_password_reset_email(user: User, link: str) -> None:
    """Goes through the email provider abstraction: failures and unconfigured email never reach the caller."""
    from apps.notifications.email import send_template

    send_template("password_reset", user.email, {"name": user.first_name, "link": link, "minutes": settings.PASSWORD_RESET_TOKEN_MINUTES}, school=user.school)


class PasswordResetService:
    @staticmethod
    def request_reset(*, email: str, request) -> None:
        """Always behaves identically to the caller (no account enumeration)."""
        email_norm = (email or "").strip().lower()
        allowed = throttling.check_and_record_password_reset(email_norm, get_client_ip(request))
        if not allowed:
            return
        user = User.objects.filter(email=email_norm, is_active=True).first()
        if user is None:
            return
        token = secrets.token_urlsafe(32)
        with transaction.atomic():
            PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            PasswordResetToken.objects.create(
                user=user,
                token_hash=_hash(token),
                expires_at=timezone.now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES),
            )
            AuditService.record(
                AuditAction.PASSWORD_RESET_REQUESTED, actor=user, entity_type="user", entity_id=user.id, request=request
            )
        send_password_reset_email(user, f"{settings.FRONTEND_ORIGIN}/reset-password?token={token}")

    @staticmethod
    def confirm_reset(*, token: str, new_password: str, request) -> None:
        invalid = ValidationError({"token": ["This reset link is invalid or has expired."]})
        record = (
            PasswordResetToken.objects.select_related("user")
            .filter(token_hash=_hash(token), used_at__isnull=True, expires_at__gt=timezone.now())
            .first()
        )
        if record is None or not record.user.is_active:
            raise invalid
        try:
            validate_password(new_password, user=record.user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc

        with transaction.atomic():
            claimed = PasswordResetToken.objects.filter(pk=record.pk, used_at__isnull=True).update(
                used_at=timezone.now()
            )
            if claimed == 0:  # lost a race with another use of the same token
                raise invalid
            user = record.user
            user.set_password(new_password)
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password", "updated_at"])
            AuthService.revoke_all_sessions(user)
            AuditService.record(
                AuditAction.PASSWORD_RESET_COMPLETED, actor=user, entity_type="user", entity_id=user.id, request=request
            )
