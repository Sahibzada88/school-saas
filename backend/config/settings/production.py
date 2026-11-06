from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, FRONTEND_ORIGIN, PROXY_SHARED_SECRET, SECRET_KEY

DEBUG = False

if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("SECRET_KEY must be set to a random value of at least 50 characters.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must list the backend hostname(s) in production.")
if not FRONTEND_ORIGIN.startswith("https://"):
    raise ImproperlyConfigured("FRONTEND_ORIGIN must be the https:// origin of the frontend.")
if len(PROXY_SHARED_SECRET) < 32:
    raise ImproperlyConfigured("PROXY_SHARED_SECRET (>= 32 chars) is required so client IPs can be trusted.")

AUTH_COOKIE_SECURE = True

# Vercel terminates TLS and forwards the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # Vercel already redirects HTTP -> HTTPS
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False  # opt in deliberately once the domain setup is final
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
