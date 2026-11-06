from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.csrf import is_valid_csrf_token
from apps.core.exceptions import InvalidCredentials
from apps.core.responses import error_envelope, success_response
from apps.core.utils import get_client_ip
from apps.tenants.services import SchoolOnboardingService

from .cookies import clear_auth_cookies, set_auth_cookies, set_csrf_cookie
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    serialize_me,
)
from .services import throttling
from .services.auth import AuthService
from .services.password_reset import PasswordResetService


class PublicAuthView(APIView):
    """Auth endpoints never parse the (possibly stale) access cookie."""

    authentication_classes: list = []
    permission_classes = [AllowAny]


class CsrfView(PublicAuthView):
    def get(self, request):
        existing = request.COOKIES.get(settings.AUTH_CSRF_COOKIE)
        response = success_response(None, message="")
        token = set_csrf_cookie(response, existing)
        response.data["data"] = {"csrf_token": token}
        return response


class RegisterView(PublicAuthView):
    def post(self, request):
        throttling.check_and_record_registration(get_client_ip(request))
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, user = SchoolOnboardingService.register(**serializer.validated_data, request=request)
        pair = AuthService.issue_tokens(user, request=request)
        response = success_response(serialize_me(user), message="School registered successfully.", status=201)
        set_auth_cookies(response, pair, request.COOKIES.get(settings.AUTH_CSRF_COOKIE))
        return response


class LoginView(PublicAuthView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, pair = AuthService.login(
            email=serializer.validated_data["email"], password=serializer.validated_data["password"], request=request
        )
        response = success_response(serialize_me(user), message="Signed in successfully.")
        set_auth_cookies(response, pair, request.COOKIES.get(settings.AUTH_CSRF_COOKIE))
        return response


class RefreshView(PublicAuthView):
    def post(self, request):
        try:
            user, pair = AuthService.refresh(
                refresh_token=request.COOKIES.get(settings.AUTH_REFRESH_COOKIE), request=request
            )
        except InvalidCredentials as exc:
            code = getattr(exc.detail, "code", "session_expired")
            response = Response(
                error_envelope(str(exc.detail), code=code, request_id=getattr(request, "request_id", None)),
                status=401,
            )
            if code != "token_rotated":  # a concurrent refresh already set fresh cookies; keep them
                clear_auth_cookies(response)
            return response
        response = success_response(serialize_me(user), message="")
        set_auth_cookies(response, pair, request.COOKIES.get(settings.AUTH_CSRF_COOKIE))
        return response


class LogoutView(PublicAuthView):
    def post(self, request):
        AuthService.logout(refresh_token=request.COOKIES.get(settings.AUTH_REFRESH_COOKIE), request=request)
        response = success_response(None, message="Signed out.")
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    def get(self, request):
        return success_response(serialize_me(request.user), message="")


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pair = AuthService.change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
            request=request,
        )
        request.user.refresh_from_db()
        response = success_response(serialize_me(request.user), message="Password changed.")
        set_auth_cookies(response, pair, request.COOKIES.get(settings.AUTH_CSRF_COOKIE))
        return response


class PasswordResetRequestView(PublicAuthView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordResetService.request_reset(email=serializer.validated_data["email"], request=request)
        return success_response(None, message="If an account exists for that email, a reset link has been sent.")


class PasswordResetConfirmView(PublicAuthView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordResetService.confirm_reset(
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
            request=request,
        )
        return success_response(None, message="Password updated. You can now sign in.")
