from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel, TenantSoftDeleteModel


class Gender(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"
    OTHER = "OTHER", "Other"


class StudentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    TRANSFERRED = "TRANSFERRED", "Transferred"
    GRADUATED = "GRADUATED", "Graduated"
    SUSPENDED = "SUSPENDED", "Suspended"


class Student(TenantSoftDeleteModel):
    student_number = models.CharField(max_length=30)
    admission_date = models.DateField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=Gender.choices)
    blood_group = models.CharField(max_length=5, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    photo = models.ForeignKey("tenants.ImageAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="student_profile")
    status = models.CharField(max_length=12, choices=StudentStatus.choices, default=StudentStatus.ACTIVE)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student_number"], condition=Q(is_deleted=False), name="uniq_student_number_active"
            )
        ]
        indexes = [
            models.Index(fields=["school", "status"], name="student_school_status_idx"),
            models.Index(fields=["school", "last_name", "first_name"], name="student_school_name_idx"),
        ]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.student_number} {self.full_name}"


class Guardian(TenantSoftDeleteModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    national_id = models.CharField(max_length=30, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="guardian_profile")

    class Meta:
        indexes = [models.Index(fields=["school", "phone"], name="guardian_school_phone_idx")]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Relationship(models.TextChoices):
    FATHER = "FATHER", "Father"
    MOTHER = "MOTHER", "Mother"
    GUARDIAN = "GUARDIAN", "Guardian"
    OTHER = "OTHER", "Other"


class StudentGuardian(TenantModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardian_links")
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="student_links")
    relationship = models.CharField(max_length=10, choices=Relationship.choices, default=Relationship.GUARDIAN)
    is_primary = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "guardian"], name="uniq_student_guardian")]
        indexes = [models.Index(fields=["school", "guardian"], name="sg_school_guardian_idx")]


class StudentDocument(TenantModel):
    """Metadata only: which paper documents the school has received. No files are stored."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=50)
    title = models.CharField(max_length=150)
    received_on = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
