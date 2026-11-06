"""
Base settings, shared by every environment.

Serverless rules baked in here:
  * no local state, no in-process caches, no background workers
  * DB connections are never reused across requests (CONN_MAX_AGE=0) because the
    runtime talks to Supabase's transaction pooler
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

try:  # .env is a local-development convenience; Vercel injects real env vars.
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass


# --------------------------------------------------------------------------- helpers
def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name, "")
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or list(default or [])


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer, got {raw!r}") from exc


# --------------------------------------------------------------------------- core
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local")
SECRET_KEY = os.environ.get("SECRET_KEY", "")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "").rstrip("/")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",  # password hashing/validation + AbstractBaseUser only (no admin, no sessions)
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.tenants",
    "apps.accounts",
    "apps.audit_logs",
    "apps.platform_admin",
    "apps.subscriptions",
    "apps.payments",
    "apps.notifications",
    "apps.students",
    "apps.teachers",
    "apps.academics",
    "apps.attendance",
    "apps.examinations",
    "apps.fees",
    "apps.reports",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.ApiHeadersMiddleware",
    "apps.core.middleware.ClientIPMiddleware",
    "apps.core.middleware.CsrfProtectionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES: list[dict] = []  # API only: no templates, no admin

# Next.js proxies URLs with trailing slashes untouched; never redirect (it breaks POST).
APPEND_SLASH = False


# --------------------------------------------------------------------------- database
def _database_config() -> dict:
    use_direct = os.environ.get("DJANGO_USE_DIRECT_URL") == "1"
    var = "DIRECT_URL" if use_direct else "DATABASE_URL"
    url = os.environ.get(var, "").strip()
    if not url:
        raise ImproperlyConfigured(
            f"{var} is not set. Copy backend/.env.example to backend/.env and fill it in."
        )
    config = dj_database_url.parse(url, conn_max_age=0, conn_health_checks=False)
    config["ATOMIC_REQUESTS"] = False  # services open transactions explicitly
    if "postgresql" in config["ENGINE"]:
        # Transaction pooler (pgbouncer-style): no server-side cursors, no prepared statements.
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
        options = config.setdefault("OPTIONS", {})
        options["prepare_threshold"] = None
        options["connect_timeout"] = env_int("DB_CONNECT_TIMEOUT", 10)
        sslmode = os.environ.get("DB_SSLMODE", "").strip()
        if sslmode:
            options["sslmode"] = sslmode
    return config


DATABASES = {"default": _database_config()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Post-migrate hardening for Supabase: RLS on every public table, no anon/authenticated grants.
ENABLE_RLS_LOCKDOWN = env_bool("ENABLE_RLS_LOCKDOWN", True)

# --------------------------------------------------------------------------- i18n
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
USE_I18N = False

# --------------------------------------------------------------------------- passwords
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- CORS / CSRF origins
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ["accept", "content-type", "x-csrf-token", "x-request-id"]
CORS_EXPOSE_HEADERS = ["X-Request-ID", "Content-Disposition"]
# Allowed values of the Origin header on unsafe requests (FRONTEND_ORIGIN is always added).
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# --------------------------------------------------------------------------- client IP
# Behind Vercel + the Next.js proxy the TCP peer is never the user. The Next middleware forwards the
# real client IP in X-Client-IP together with X-Proxy-Secret; the backend trusts it only if the secret matches.
PROXY_SHARED_SECRET = os.environ.get("PROXY_SHARED_SECRET", "")
TRUSTED_IP_HEADER = os.environ.get("TRUSTED_IP_HEADER", "")  # optional Django META key, e.g. HTTP_X_FORWARDED_FOR

# --------------------------------------------------------------------------- auth / JWT / cookies
JWT_SIGNING_KEY = os.environ.get("JWT_SIGNING_KEY", "")  # falls back to SECRET_KEY
ACCESS_TOKEN_MINUTES = env_int("ACCESS_TOKEN_MINUTES", 15)
REFRESH_TOKEN_DAYS = env_int("REFRESH_TOKEN_DAYS", 7)
REFRESH_REUSE_GRACE_SECONDS = env_int("REFRESH_REUSE_GRACE_SECONDS", 10)  # concurrent-tab tolerance
PASSWORD_RESET_TOKEN_MINUTES = env_int("PASSWORD_RESET_TOKEN_MINUTES", 30)

AUTH_ACCESS_COOKIE = "access_token"
AUTH_REFRESH_COOKIE = "refresh_token"
AUTH_HINT_COOKIE = "sid_hint"  # non-secret "a session probably exists" flag read by Next middleware
AUTH_CSRF_COOKIE = "csrf_token"
AUTH_REFRESH_COOKIE_PATH = "/api/v1/auth/"
AUTH_COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "") or None
AUTH_COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_SECURE = env_bool("COOKIE_SECURE", True)

# --------------------------------------------------------------------------- email
_EMAIL_BACKENDS = {
    "console": "django.core.mail.backends.console.EmailBackend",
    "smtp": "django.core.mail.backends.smtp.EmailBackend",
}
_email_choice = os.environ.get("EMAIL_BACKEND", "console").strip() or "console"
if _email_choice not in _EMAIL_BACKENDS:
    raise ImproperlyConfigured("EMAIL_BACKEND must be 'console' or 'smtp'.")
EMAIL_BACKEND = _EMAIL_BACKENDS[_email_choice]
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.environ.get("EMAIL_FROM", "") or "School SaaS <no-reply@localhost>"

# --------------------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["apps.core.renderers.EnvelopeJSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.CookieJWTAuthentication"],
    # Deny by default: public endpoints must opt in with AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# --------------------------------------------------------------------------- logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
}
