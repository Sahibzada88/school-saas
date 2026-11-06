"""Signed double-submit CSRF tokens.

The token lives in a JS-readable cookie and must be echoed in the X-CSRF-Token header on every unsafe
request. It is HMAC-signed, so a cookie injected by a sibling subdomain (which cannot know SECRET_KEY)
is rejected.
"""
import hashlib
import hmac
import secrets

from django.conf import settings


def _sign(nonce: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"csrf:{nonce}".encode(), hashlib.sha256).hexdigest()


def generate_csrf_token() -> str:
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_sign(nonce)}"


def is_valid_csrf_token(token: str | None) -> bool:
    if not token or token.count(".") != 1:
        return False
    nonce, signature = token.split(".")
    return hmac.compare_digest(signature.encode(), _sign(nonce).encode())


def csrf_tokens_match(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    if not hmac.compare_digest(cookie_value.encode(), header_value.encode()):
        return False
    return is_valid_csrf_token(cookie_value)
