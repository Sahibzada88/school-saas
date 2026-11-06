import logging

from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from .responses import error_envelope

logger = logging.getLogger(__name__)


class DomainError(APIException):
    """Business-rule violation raised from services. Subclass for specific codes/statuses."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request could not be completed."
    default_code = "domain_error"


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


class InvalidCredentials(APIException):
    """401 that DRF will not coerce to 403 (used where no authenticator header exists)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid email or password."
    default_code = "invalid_credentials"


class TooManyRequests(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Too many attempts. Please try again later."
    default_code = "too_many_requests"


class SchoolDisabled(PermissionDenied):
    default_detail = "Your school account has been temporarily disabled. Please contact platform administration."
    default_code = "school_disabled"


class SubscriptionExpired(APIException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Your subscription has expired. Your data is read-only until it is renewed."
    default_code = "subscription_expired"


class SubscriptionBlocked(PermissionDenied):
    default_detail = "Access is blocked because the school's subscription is not active. Please contact platform administration."
    default_code = "subscription_blocked"


class PlanLimitReached(PermissionDenied):
    default_detail = "Your plan's limit has been reached. Contact platform administration to upgrade."
    default_code = "plan_limit_reached"


class ExportTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "This export is too large for one request. Narrow the filters (class, section or dates) and try again."
    default_code = "export_too_large"


class PasswordChangeRequired(PermissionDenied):
    default_detail = "You must change your password before continuing."
    default_code = "password_change_required"


def api_exception_handler(exc, context):
    """Convert every exception into the standard error envelope without leaking internals."""
    request = context.get("request")
    request_id = getattr(request, "request_id", None)

    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled exception (request_id=%s)", request_id)
        set_rollback()
        return Response(
            error_envelope(
                "An unexpected error occurred.",
                code="server_error",
                request_id=request_id,
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.data
    if isinstance(exc, ValidationError):
        message = "Validation failed."
        errors = data if isinstance(data, dict) else {"non_field_errors": data}
        code = "validation_error"
    else:
        detail = data.get("detail") if isinstance(data, dict) else None
        message = str(detail) if detail else "Request failed."
        errors = {}
        code = getattr(detail, "code", None) or getattr(exc, "default_code", None)

    response.data = error_envelope(message, errors=errors, code=code, request_id=request_id)
    return response
