from django.conf import settings

from apps.core.csrf import generate_csrf_token, is_valid_csrf_token


def _common() -> dict:
    return {
        "domain": settings.AUTH_COOKIE_DOMAIN,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }


def set_csrf_cookie(response, existing: str | None = None) -> str:
    token = existing if is_valid_csrf_token(existing) else generate_csrf_token()
    response.set_cookie(
        settings.AUTH_CSRF_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_DAYS * 86400,
        path="/",
        httponly=False,  # must be readable by JS to be echoed in the header
        **_common(),
    )
    return token


def set_auth_cookies(response, pair, existing_csrf: str | None = None) -> None:
    refresh_age = settings.REFRESH_TOKEN_DAYS * 86400
    response.set_cookie(
        settings.AUTH_ACCESS_COOKIE, pair.access,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60, path="/", httponly=True, **_common(),
    )
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE, pair.refresh,
        max_age=refresh_age, path=settings.AUTH_REFRESH_COOKIE_PATH, httponly=True, **_common(),
    )
    response.set_cookie(settings.AUTH_HINT_COOKIE, "1", max_age=refresh_age, path="/", httponly=False, **_common())
    set_csrf_cookie(response, existing_csrf)


def clear_auth_cookies(response) -> None:
    common = {"domain": settings.AUTH_COOKIE_DOMAIN, "samesite": settings.AUTH_COOKIE_SAMESITE}
    response.delete_cookie(settings.AUTH_ACCESS_COOKIE, path="/", **common)
    response.delete_cookie(settings.AUTH_REFRESH_COOKIE, path=settings.AUTH_REFRESH_COOKIE_PATH, **common)
    response.delete_cookie(settings.AUTH_HINT_COOKIE, path="/", **common)
