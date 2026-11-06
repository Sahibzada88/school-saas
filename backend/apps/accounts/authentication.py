import uuid

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import AuthSession
from .services.tokens import TokenError, decode_token


class CookieJWTAuthentication(BaseAuthentication):
    """Reads the HttpOnly access-token cookie. Every request re-checks the session row (so logout,
    password change and deactivation take effect immediately) and loads the user + school in one query."""

    def authenticate_header(self, request):
        return 'Cookie realm="api"'

    def authenticate(self, request):
        token = request.COOKIES.get(settings.AUTH_ACCESS_COOKIE)
        if not token:
            return None
        try:
            payload = decode_token(token, "access")
            sid = uuid.UUID(str(payload.get("sid", "")))
        except (TokenError, ValueError) as exc:
            raise AuthenticationFailed("Your session has expired.", code="token_expired") from exc

        session = AuthSession.objects.select_related("user__school__subscription").filter(id=sid, revoked_at__isnull=True).first()
        if session is None or str(session.user_id) != payload["sub"]:
            raise AuthenticationFailed("Your session has expired.", code="token_expired")
        if not session.user.is_active:
            raise AuthenticationFailed("This account is disabled.", code="user_inactive")
        return session.user, payload
