from datetime import timedelta

import jwt
from django.conf import settings
from django.utils import timezone

ALGORITHM = "HS256"
LEEWAY_SECONDS = 10  # clock skew between serverless instances


class TokenError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason  # "expired" | "invalid"


def _key() -> str:
    return settings.JWT_SIGNING_KEY or settings.SECRET_KEY


def encode_token(*, typ: str, sub, lifetime: timedelta, **claims) -> str:
    now = timezone.now()
    payload = {
        "typ": typ,
        "sub": str(sub),
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        **claims,
    }
    return jwt.encode(payload, _key(), algorithm=ALGORITHM)


def decode_token(token: str, typ: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            _key(),
            algorithms=[ALGORITHM],
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("invalid") from exc
    if payload.get("typ") != typ:
        raise TokenError("invalid")
    return payload
