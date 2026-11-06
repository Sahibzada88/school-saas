import uuid

from django.db import models
from django.utils import timezone

from .managers import (
    AllObjectsManager,
    SoftDeleteManager,
    TenantAllObjectsManager,
    TenantManager,
    TenantSoftDeleteManager,
)


class UUIDTimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Soft-deletable mixin.

    * `objects` excludes deleted rows; `all_objects` includes them.
    * `delete()` soft-deletes; `hard_delete()` really deletes.
    * Unique constraints on soft-deletable models must be partial (condition=Q(is_deleted=False)).
    * Queryset-level soft delete uses update(), so it does not touch `updated_at`.
    """

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()


class TenantModel(UUIDTimestampedModel):
    """Base for every school-owned record. `school` is not editable, so serializers can never accept it
    from the client; it is injected server-side from the authenticated user."""

    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="+", editable=False)

    objects = TenantManager()

    class Meta:
        abstract = True


class TenantSoftDeleteModel(TenantModel, SoftDeleteModel):
    objects = TenantSoftDeleteManager()
    all_objects = TenantAllObjectsManager()

    class Meta:
        abstract = True
