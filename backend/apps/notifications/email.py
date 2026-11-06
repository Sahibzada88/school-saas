"""Email provider abstraction. Sending never raises into the caller (a mail outage must not break sign-up, payments or
password resets) and every attempt is logged. Providers: Django's mail backend (console/SMTP) or a no-op when email
is not configured. Swap in an API provider later by adding a class and returning it from get_provider()."""
import logging
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import send_mail

from .email_templates import TEMPLATES
from .models import EmailLog

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None: ...


class DjangoMailProvider(EmailProvider):
    def send(self, to: str, subject: str, body: str) -> None:
        send_mail(subject=subject, message=body, from_email=None, recipient_list=[to], fail_silently=False)


class NullProvider(EmailProvider):
    def send(self, to: str, subject: str, body: str) -> None:  # pragma: no cover - intentionally empty
        return None


def get_provider() -> EmailProvider | None:
    """None = email is not configured (console backend outside DEBUG would only leak links into server logs)."""
    if settings.EMAIL_BACKEND.endswith("console.EmailBackend") and not settings.DEBUG:
        return None
    return DjangoMailProvider()


def send_template(template: str, to: str, context: dict, *, school=None) -> bool:
    subject, body = TEMPLATES[template]
    provider = get_provider()
    if provider is None:
        EmailLog.objects.create(to_email=to, template=template, status="SKIPPED", error="Email is not configured.", school=school)
        logger.warning("Email '%s' skipped: not configured.", template)
        return False
    try:
        provider.send(to, subject, body.format(**context))
    except Exception as exc:  # never propagate
        logger.exception("Failed to send email '%s'", template)
        EmailLog.objects.create(to_email=to, template=template, status="FAILED", error=str(exc)[:300], school=school)
        return False
    EmailLog.objects.create(to_email=to, template=template, status="SENT", school=school)
    return True
