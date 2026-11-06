import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .responses import Envelope, error_envelope, success_response

logger = logging.getLogger(__name__)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    """Liveness probe. `?db=1` also runs `SELECT 1` against PostgreSQL."""
    payload = {
        "status": "ok",
        "time": timezone.now().isoformat(),
        "environment": settings.ENVIRONMENT,
    }
    if request.query_params.get("db") == "1":
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            payload["database"] = "ok"
        except Exception:  # never leak connection details
            logger.exception("Health check: database unreachable (request_id=%s)", request.request_id)
            return Response(
                error_envelope(
                    "Database is unavailable.",
                    code="database_unavailable",
                    request_id=request.request_id,
                ),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
    return success_response(payload, message="OK")


def not_found(request, exception=None):
    body = error_envelope(
        "The requested resource was not found.",
        code="not_found",
        request_id=getattr(request, "request_id", None),
    )
    return JsonResponse(dict(body), status=404)


def server_error(request):
    body = error_envelope(
        "An unexpected error occurred.",
        code="server_error",
        request_id=getattr(request, "request_id", None),
    )
    return JsonResponse(dict(body), status=500)
