from django.conf import settings
from django.db import models

from apps.core.models import TenantModel, UUIDTimestampedModel


class SchoolStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    INACTIVE = "INACTIVE", "Inactive"


class School(UUIDTimestampedModel):
    """Tenant root. Never hard-deleted: deactivation only restricts access (school.status),
    it is independent of the subscription status added in Phase 4."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=12, choices=SchoolStatus.choices, default=SchoolStatus.ACTIVE)
    status_reason = models.TextField(blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Karachi")
    currency = models.CharField(max_length=3, default="PKR")
    logo = models.ForeignKey("tenants.ImageAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"], name="school_status_idx"),
            models.Index(fields=["created_at"], name="school_created_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_accessible(self) -> bool:
        return self.status == SchoolStatus.ACTIVE


class SchoolSettings(UUIDTimestampedModel):
    school = models.OneToOneField(School, on_delete=models.PROTECT, related_name="settings")
    student_number_prefix = models.CharField(max_length=10, default="STU")
    invoice_prefix = models.CharField(max_length=10, default="INV")
    receipt_prefix = models.CharField(max_length=10, default="RCT")
    week_start = models.PositiveSmallIntegerField(default=1)  # 0=Sunday .. 6=Saturday
    extra = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Settings of {self.school_id}"


class ImageAsset(TenantModel):
    """Base64 image stored in PostgreSQL (no object storage). Listed separately from entities so list queries never
    drag image data into memory. Validation/limits live in apps/core/images.py."""

    kind = models.CharField(max_length=10, default="photo")
    mime_type = models.CharField(max_length=30)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    byte_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    data_base64 = models.TextField()


class NumberSequence(TenantModel):
    """Per-school counters (STUDENT, EMPLOYEE, INVOICE, RECEIPT). Allocated with SELECT ... FOR UPDATE."""

    key = models.CharField(max_length=20)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "key"], name="uniq_number_sequence")]
