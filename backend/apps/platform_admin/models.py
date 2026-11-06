from django.conf import settings
from django.db import models

from apps.core.models import UUIDTimestampedModel


class PlatformSetting(UUIDTimestampedModel):
    """Platform-wide tunables stored as data (never hard-coded): see apps/platform_admin/config.py for the catalogue."""

    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self) -> str:
        return self.key
