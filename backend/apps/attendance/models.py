from django.conf import settings
from django.db import models

from apps.core.models import TenantModel


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    LEAVE = "LEAVE", "Leave"


class StudentAttendance(TenantModel):
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="attendance")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT, related_name="attendance")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=8, choices=AttendanceStatus.choices)
    remarks = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="uniq_student_attendance_day")]
        indexes = [
            models.Index(fields=["school", "section", "date"], name="att_school_section_date_idx"),
            models.Index(fields=["school", "student", "date"], name="att_school_student_date_idx"),
        ]


class TeacherAttendance(TenantModel):
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.PROTECT, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=8, choices=AttendanceStatus.choices)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["teacher", "date"], name="uniq_teacher_attendance_day")]
        indexes = [models.Index(fields=["school", "date"], name="tatt_school_date_idx")]
