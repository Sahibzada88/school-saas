import os

from django.core.wsgi import get_wsgi_application

# Vercel runs this module as the serverless entrypoint (settings.WSGI_APPLICATION). Vercel sets VERCEL=1 at build and
# at runtime. It also executes manage.py to "discover" a settings module, which would be the local one, so on Vercel
# we assign (not setdefault) to guarantee production settings (DEBUG off, secure cookies, strict validation).
if os.environ.get("VERCEL"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_wsgi_application()
