"""Vercel serverless entrypoint. Vercel's Python runtime serves the WSGI callable named `app`."""
import os
import sys
from pathlib import Path

# Make `config` and `apps` importable regardless of the runtime's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
