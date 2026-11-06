"""Shared helpers for backend tests."""
import secrets

from django.conf import settings
from django.utils.text import slugify
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.subscriptions.services import SubscriptionService
from apps.tenants.models import School, SchoolSettings

from .csrf import generate_csrf_token

TEST_PASSWORD = "Str0ng-Test-Pass#2026"


def make_school(name: str = "Test School", with_defaults: bool = True, **fields) -> School:
    fields.setdefault("email", f"{secrets.token_hex(3)}@school.test")
    fields.setdefault("country", "Pakistan")
    fields.setdefault("city", "Islamabad")
    school = School.objects.create(name=name, slug=f"{slugify(name)}-{secrets.token_hex(3)}", **fields)
    SchoolSettings.objects.create(school=school)
    SubscriptionService.start_trial(school)
    if with_defaults:
        from apps.tenants.defaults import bootstrap_school

        bootstrap_school(school)
    return school


def make_user(school=None, role: str = Role.SCHOOL_ADMIN, email: str | None = None, password: str = TEST_PASSWORD, **extra) -> User:
    if role == Role.SUPER_ADMIN:
        school = None
    extra.setdefault("first_name", "Test")
    extra.setdefault("last_name", role.title())
    return User.objects.create_user(
        email=email or f"{role.lower()}-{secrets.token_hex(3)}@example.test",
        password=password,
        role=role,
        school=school,
        **extra,
    )


def api_client() -> APIClient:
    """Client that already carries a valid CSRF cookie + header (like the browser after /auth/csrf/)."""
    client = APIClient()
    token = generate_csrf_token()
    client.cookies[settings.AUTH_CSRF_COOKIE] = token
    client.defaults["HTTP_X_CSRF_TOKEN"] = token
    return client


def login_client(user: User, password: str = TEST_PASSWORD) -> APIClient:
    client = api_client()
    response = client.post("/api/v1/auth/login/", {"email": user.email, "password": password})
    assert response.status_code == 200, response.content
    return client


def iter_routed_views(url_prefix: str):
    """Yield (route, view_class) for every URL pattern whose route starts with `url_prefix`."""
    from django.urls import URLResolver, get_resolver

    def walk(patterns, route):
        for pattern in patterns:
            full = route + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                yield from walk(pattern.url_patterns, full)
            else:
                yield full, pattern.callback

    for route, callback in walk(get_resolver().url_patterns, ""):
        if route.startswith(url_prefix):
            yield route, (getattr(callback, "cls", None) or getattr(callback, "view_class", None))


def png_data_url(size=(10, 10), color="red", fmt="PNG") -> str:
    """A real, tiny image as a base64 data URL (what the frontend uploads)."""
    import base64
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[fmt]
    return f"data:{mime};base64,{base64.b64encode(buffer.getvalue()).decode()}"


def staff_client(school, role):
    """(user, logged-in client) for a school user of the given role."""
    user = make_user(school, role)
    return user, login_client(user)
