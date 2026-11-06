import hmac
import ipaddress

from django.conf import settings


def _valid_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def get_client_ip(request) -> str | None:
    """Best-effort client IP, in order of trust:

    1. X-Client-IP, but only when X-Proxy-Secret matches PROXY_SHARED_SECRET (set by the Next.js proxy).
    2. TRUSTED_IP_HEADER (a Django META key) if configured.
    3. REMOTE_ADDR.
    Client-supplied X-Forwarded-For / X-Client-IP are never trusted on their own.
    """
    secret = getattr(settings, "PROXY_SHARED_SECRET", "")
    if secret:
        supplied = request.META.get("HTTP_X_PROXY_SECRET", "")
        if supplied and hmac.compare_digest(supplied.encode(), secret.encode()):
            ip = _valid_ip(request.META.get("HTTP_X_CLIENT_IP", ""))
            if ip:
                return ip

    header = getattr(settings, "TRUSTED_IP_HEADER", "")
    if header:
        ip = _valid_ip(request.META.get(header, "").split(",")[0])
        if ip:
            return ip

    return _valid_ip(request.META.get("REMOTE_ADDR", ""))
