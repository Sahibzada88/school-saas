import random
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import InvalidCredentials
from apps.core.utils import get_client_ip

from ..models import AttemptScope, AuthSession, User
from . import throttling
from .tokens import TokenError, decode_token, encode_token


@dataclass
class TokenPair:
    access: str
    refresh: str
    session: AuthSession


class AuthService:
    # ------------------------------------------------------------------ issuing
    @staticmethod
    def issue_tokens(user: User, *, request=None, family_id=None) -> TokenPair:
        now = timezone.now()
        refresh_lifetime = timedelta(days=settings.REFRESH_TOKEN_DAYS)
        jti = uuid.uuid4().hex
        family = family_id or uuid.uuid4()
        session = AuthSession.objects.create(
            user=user,
            family_id=family,
            refresh_jti=jti,
            expires_at=now + refresh_lifetime,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request is not None else ""),
            ip=get_client_ip(request) if request is not None else None,
        )
        access = encode_token(
            typ="access",
            sub=user.id,
            lifetime=timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
            sid=str(session.id),
            jti=uuid.uuid4().hex,
        )
        refresh = encode_token(typ="refresh", sub=user.id, lifetime=refresh_lifetime, jti=jti, fam=str(family))
        return TokenPair(access=access, refresh=refresh, session=session)

    # ------------------------------------------------------------------ login
    @staticmethod
    def login(*, email: str, password: str, request) -> tuple[User, TokenPair]:
        email_norm = (email or "").strip().lower()
        ip = get_client_ip(request)
        throttling.check_login_allowed(email_norm, ip)

        user = User.objects.select_related("school").filter(email=email_norm).first()
        if user is None:
            make_password(password)  # equalise timing with the real check
            valid = False
        else:
            valid = user.check_password(password) and user.is_active

        if not valid:
            throttling.record_attempt(AttemptScope.LOGIN, email_norm=email_norm, ip=ip, succeeded=False)
            raise InvalidCredentials()

        throttling.record_attempt(AttemptScope.LOGIN, email_norm=email_norm, ip=ip, succeeded=True)
        with transaction.atomic():
            User.objects.filter(pk=user.pk).update(last_login=timezone.now())
            pair = AuthService.issue_tokens(user, request=request)
            AuditService.record(AuditAction.LOGIN, actor=user, entity_type="user", entity_id=user.id, request=request)
        if random.random() < 0.02:  # opportunistic cleanup of long-expired sessions
            AuthSession.objects.filter(expires_at__lt=timezone.now() - timedelta(days=7)).delete()
        return user, pair

    # ------------------------------------------------------------------ refresh (rotation + reuse detection)
    @staticmethod
    def refresh(*, refresh_token: str | None, request) -> tuple[User, TokenPair]:
        if not refresh_token:
            raise InvalidCredentials("Your session has expired. Please sign in again.", code="session_expired")
        try:
            payload = decode_token(refresh_token, "refresh")
        except TokenError as exc:
            raise InvalidCredentials("Your session has expired. Please sign in again.", code="session_expired") from exc

        outcome, result = AuthService._rotate(payload, request)  # commits before any raise below
        if outcome == "ok":
            return result
        if outcome == "rotated":
            raise InvalidCredentials("Session was just refreshed. Retry the request.", code="token_rotated")
        raise InvalidCredentials("Your session has expired. Please sign in again.", code="session_expired")

    @staticmethod
    def _rotate(payload: dict, request):
        now = timezone.now()
        with transaction.atomic():
            session = (
                AuthSession.objects.select_for_update(of=("self",))
                .select_related("user__school")
                .filter(refresh_jti=payload.get("jti", ""))
                .first()
            )
            if session is None or session.revoked_at is not None or session.expires_at <= now:
                return "invalid", None

            if session.rotated_at is not None:
                if now - session.rotated_at <= timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS):
                    return "rotated", None  # concurrent tab/retry: do not punish
                AuthSession.objects.filter(family_id=session.family_id, revoked_at__isnull=True).update(revoked_at=now)
                AuditService.record(
                    AuditAction.TOKEN_REUSE_DETECTED, actor=session.user, entity_type="user",
                    entity_id=session.user_id, request=request,
                )
                return "reuse", None

            user = session.user
            if not user.is_active:
                AuthSession.objects.filter(family_id=session.family_id, revoked_at__isnull=True).update(revoked_at=now)
                return "invalid", None

            session.rotated_at = now
            session.save(update_fields=["rotated_at", "updated_at"])
            pair = AuthService.issue_tokens(user, request=request, family_id=session.family_id)
            return "ok", (user, pair)

    # ------------------------------------------------------------------ logout / revocation
    @staticmethod
    def logout(*, refresh_token: str | None, request) -> None:
        if not refresh_token:
            return
        try:
            payload = decode_token(refresh_token, "refresh")
        except TokenError:
            return
        session = AuthSession.objects.select_related("user").filter(refresh_jti=payload.get("jti", "")).first()
        if session is None:
            return
        with transaction.atomic():
            AuthSession.objects.filter(family_id=session.family_id, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
            AuditService.record(
                AuditAction.LOGOUT, actor=session.user, entity_type="user", entity_id=session.user_id, request=request
            )

    @staticmethod
    def revoke_all_sessions(user: User) -> int:
        return AuthSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())

    # ------------------------------------------------------------------ password change
    @staticmethod
    def change_password(*, user: User, current_password: str, new_password: str, request) -> TokenPair:
        if not user.check_password(current_password):
            raise ValidationError({"current_password": ["Current password is incorrect."]})
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)}) from exc
        with transaction.atomic():
            user.set_password(new_password)
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password", "updated_at"])
            AuthService.revoke_all_sessions(user)
            pair = AuthService.issue_tokens(user, request=request)
            AuditService.record(
                AuditAction.PASSWORD_CHANGED, actor=user, entity_type="user", entity_id=user.id, request=request
            )
        return pair
