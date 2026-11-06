import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel, TenantSoftDeleteModel


class NotificationType(models.TextChoices):
    TRIAL_STARTED = "TRIAL_STARTED", "Trial started"
    TRIAL_EXPIRING = "TRIAL_EXPIRING", "Trial expiring"
    TRIAL_EXPIRED = "TRIAL_EXPIRED", "Trial expired"
    SUBSCRIPTION_ACTIVATED = "SUBSCRIPTION_ACTIVATED", "Subscription activated"
    SUBSCRIPTION_EXPIRING = "SUBSCRIPTION_EXPIRING", "Subscription expiring"
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED", "Subscription expired"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "Payment received"
    SUBSCRIPTION_EXTENDED = "SUBSCRIPTION_EXTENDED", "Subscription extended"
    SCHOOL_ACTIVATED = "SCHOOL_ACTIVATED", "School activated"
    SCHOOL_SUSPENDED = "SCHOOL_SUSPENDED", "School suspended"
    SCHOOL_DEACTIVATED = "SCHOOL_DEACTIVATED", "School deactivated"
    SCHOOL_REACTIVATED = "SCHOOL_REACTIVATED", "School reactivated"
    ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
    FEE_REMINDER = "FEE_REMINDER", "Fee reminder"
    ABSENCE_ALERT = "ABSENCE_ALERT", "Absence alert"


class Severity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


class Notification(models.Model):
    """Per-recipient notification. `dedupe_key` makes lazy, request-time generation idempotent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    school = models.ForeignKey("tenants.School", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    type = models.CharField(max_length=30, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    data = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=200, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"],
                condition=Q(dedupe_key__isnull=False),
                name="uniq_notification_dedupe",
            )
        ]
        indexes = [models.Index(fields=["recipient", "is_read", "created_at"], name="notif_recipient_idx")]


class AnnouncementAudience(models.TextChoices):
    ALL = "ALL", "Everyone"
    STAFF = "STAFF", "All staff"
    TEACHERS = "TEACHERS", "Teachers"
    PARENTS = "PARENTS", "Parents"
    STUDENTS = "STUDENTS", "Students"
    CLASS = "CLASS", "One class"


class Announcement(TenantSoftDeleteModel):
    """A school notice board entry. Shown as a feed filtered by audience at read time; read receipts are lazy
    (AnnouncementRead), so posting to thousands of parents never fans out into thousands of rows."""

    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=10, choices=AnnouncementAudience.choices, default=AnnouncementAudience.ALL)
    school_class = models.ForeignKey("academics.SchoolClass", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        indexes = [models.Index(fields=["school", "published_at"], name="announce_school_pub_idx")]


class AnnouncementRead(TenantModel):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["announcement", "user"], name="uniq_announcement_read")]


class EmailLog(models.Model):
    """Append-only trail of outgoing emails (also records skipped sends when email is not configured)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    to_email = models.EmailField()
    template = models.CharField(max_length=50)
    status = models.CharField(max_length=10)  # SENT | FAILED | SKIPPED
    error = models.CharField(max_length=300, blank=True)
    school = models.ForeignKey("tenants.School", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
