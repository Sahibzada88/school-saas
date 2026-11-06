import re
import uuid

from django.conf import settings
from django.http import JsonResponse

from .csrf import csrf_tokens_match
from .responses import error_envelope
from .utils import get_client_ip

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class RequestIdMiddleware:
    """Attach a request id (client-supplied if well-formed, else generated) for log/error correlation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request.request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class ApiHeadersMiddleware:
    """Conservative defaults for an API: never cache, no referrer. Views may override (e.g. images)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


class ClientIPMiddleware:
    """Resolve the client IP once (see utils.get_client_ip) and expose it as request.client_ip."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.client_ip = get_client_ip(request)
        return self.get_response(request)


class CsrfProtectionMiddleware:
    """CSRF defence for every unsafe /api/ request, including unauthenticated ones (login CSRF).

    1. If an Origin header is present it must be a trusted origin.
    2. The X-CSRF-Token header must equal the signed csrf cookie.
    Centralised here so no view can forget it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _trusted_origins() -> set[str]:
        origins = {o.rstrip("/") for o in settings.CSRF_TRUSTED_ORIGINS}
        if settings.FRONTEND_ORIGIN:
            origins.add(settings.FRONTEND_ORIGIN.rstrip("/"))
        return origins

    def _failure(self, request) -> str | None:
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") not in self._trusted_origins():
            return "Request origin is not allowed."
        cookie = request.COOKIES.get(settings.AUTH_CSRF_COOKIE)
        header = request.headers.get("X-CSRF-Token")
        if not csrf_tokens_match(cookie, header):
            return "CSRF token missing or invalid."
        return None

    def __call__(self, request):
        if request.path.startswith("/api/") and request.method not in _SAFE_METHODS:
            message = self._failure(request)
            if message:
                body = error_envelope(
                    message, code="csrf_failed", request_id=getattr(request, "request_id", None)
                )
                return JsonResponse(dict(body), status=403)
        return self.get_response(request)
