from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Soft delete. Use hard_delete() for a real DELETE."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: soft-deleted rows never appear in normal queries."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Explicit opt-in manager that includes soft-deleted rows."""


class TenantQuerySet(models.QuerySet):
    def for_school(self, school):
        """The only sanctioned way to scope a query. Refuses a missing tenant instead of leaking all rows."""
        if school is None:
            raise ValueError("A school is required for tenant-scoped queries.")
        return self.filter(school=school)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    pass


class TenantSoftDeleteQuerySet(TenantQuerySet, SoftDeleteQuerySet):
    pass


class TenantSoftDeleteManager(models.Manager.from_queryset(TenantSoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class TenantAllObjectsManager(models.Manager.from_queryset(TenantSoftDeleteQuerySet)):
    pass
