from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import Role

from .models import Notification, Severity


class NotificationService:
    @staticmethod
    def notify_school_admins(
        school,
        *,
        type: str,
        title: str,
        body: str = "",
        severity: str = Severity.INFO,
        data: dict | None = None,
        dedupe_key: str | None = None,
        email_template: str | None = None,
        email_context: dict | None = None,
    ) -> int:
        """Create one notification per active School Admin of `school` (billing/lifecycle notices go to admins only).

        With a `dedupe_key` this is idempotent: concurrent requests, repeated dashboard loads or retries cannot create
        duplicates (checked up front to skip needless writes, and enforced by a partial unique constraint)."""
        if dedupe_key and Notification.objects.filter(school=school, dedupe_key=dedupe_key).exists():
            return 0
        admins = list(User.objects.filter(school=school, role=Role.SCHOOL_ADMIN, is_active=True))
        admin_ids = [a.id for a in admins]
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_id=admin_id, school=school, type=type, title=title, body=body,
                    severity=severity, data=data or {}, dedupe_key=dedupe_key,
                )
                for admin_id in admin_ids
            ],
            ignore_conflicts=True,
        )
        if email_template:
            from .email import send_template  # lazy: keeps imports light for callers that never email

            for admin in admins:
                send_template(email_template, admin.email, {"name": admin.first_name, **(email_context or {})}, school=school)
        return len(admin_ids)

    @staticmethod
    def notify_users(
        school,
        users,
        *,
        type: str,
        title: str,
        body: str = "",
        severity: str = Severity.INFO,
        data: dict | None = None,
        dedupe_key: str | None = None,
        email_template: str | None = None,
        email_context: dict | None = None,
    ) -> int:
        """Notify specific users (e.g. the parents of one student). Idempotent per recipient when `dedupe_key` is set.
        Returns how many recipients were newly notified; each of them also gets the optional email (never raises)."""
        users = list({u.id: u for u in users}.values())
        if dedupe_key:
            existing = set(Notification.objects.filter(recipient__in=users, dedupe_key=dedupe_key).values_list("recipient_id", flat=True))
            users = [u for u in users if u.id not in existing]
        if not users:
            return 0
        Notification.objects.bulk_create(
            [
                Notification(recipient=u, school=school, type=type, title=title, body=body, severity=severity, data=data or {}, dedupe_key=dedupe_key)
                for u in users
            ],
            ignore_conflicts=True,
        )
        if email_template:
            from .email import send_template

            for u in users:
                if u.email:
                    send_template(email_template, u.email, {"name": u.first_name, **(email_context or {})}, school=school)
        return len(users)

    @staticmethod
    def mark_read(queryset) -> int:
        return queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
