import sys

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS as _ALLOWED_HOSTS
from .base import CORS_ALLOWED_ORIGINS as _CORS
from .base import CSRF_TRUSTED_ORIGINS as _CSRF
from .base import SECRET_KEY as _SECRET_KEY
from .base import env_bool

DEBUG = env_bool("DEBUG", True)
SECRET_KEY = _SECRET_KEY or "local-dev-only-insecure-key-do-not-use-in-production"
ALLOWED_HOSTS = _ALLOWED_HOSTS or ["localhost", "127.0.0.1", "backend"]
CORS_ALLOWED_ORIGINS = _CORS or ["http://localhost:3000"]
CSRF_TRUSTED_ORIGINS = _CSRF or ["http://localhost:3000"]
AUTH_COOKIE_SECURE = env_bool("COOKIE_SECURE", False)  # plain http on localhost

# Faster hashing in local/test runs only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
