from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantSoftDeleteModel
from apps.students.models import Gender


class TeacherStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ON_LEAVE = "ON_LEAVE", "On leave"
    RESIGNED = "RESIGNED", "Resigned"
    TERMINATED = "TERMINATED", "Terminated"


class Teacher(TenantSoftDeleteModel):
    employee_id = models.CharField(max_length=30)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    qualification = models.CharField(max_length=150, blank=True)
    joining_date = models.DateField()
    photo = models.ForeignKey("tenants.ImageAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="teacher_profile")
    status = models.CharField(max_length=12, choices=TeacherStatus.choices, default=TeacherStatus.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "employee_id"], condition=Q(is_deleted=False), name="uniq_employee_id_active")
        ]
        indexes = [models.Index(fields=["school", "status"], name="teacher_school_status_idx")]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
