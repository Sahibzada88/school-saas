from django.db import models
from django.db.models import F, Q

from apps.core.models import TenantModel, TenantSoftDeleteModel


class AcademicSession(TenantSoftDeleteModel):
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], condition=Q(is_deleted=False), name="uniq_session_name_active"),
            models.UniqueConstraint(fields=["school"], condition=Q(is_current=True, is_deleted=False), name="uniq_current_session"),
            models.CheckConstraint(condition=Q(end_date__gt=F("start_date")), name="session_dates_valid"),
        ]
        ordering = ["-start_date"]


class SchoolClass(TenantSoftDeleteModel):
    name = models.CharField(max_length=50)
    level_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "name"], condition=Q(is_deleted=False), name="uniq_class_name_active")]
        ordering = ["level_order", "name"]

    def __str__(self) -> str:
        return self.name


class Section(TenantSoftDeleteModel):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name="sections")
    name = models.CharField(max_length=30)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    class_teacher = models.ForeignKey("teachers.Teacher", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school_class", "name"], condition=Q(is_deleted=False), name="uniq_section_name_active")]
        ordering = ["school_class__level_order", "name"]


class Subject(TenantSoftDeleteModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "code"], condition=Q(is_deleted=False), name="uniq_subject_code_active")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ClassSubject(TenantModel):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="class_subjects")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="class_subjects")
    is_optional = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school_class", "subject"], name="uniq_class_subject")]


class TeacherAssignment(TenantModel):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="assignments")
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="assignments")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="assignments")
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.CASCADE, related_name="assignments")
    is_class_teacher = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "teacher", "section", "subject"], name="uniq_assignment"),
            models.UniqueConstraint(fields=["session", "teacher", "section"], condition=Q(subject__isnull=True), name="uniq_assignment_no_subject"),
        ]
        indexes = [
            models.Index(fields=["school", "teacher"], name="assign_school_teacher_idx"),
            models.Index(fields=["school", "section"], name="assign_school_section_idx"),
        ]


class EnrollmentStatus(models.TextChoices):
    ENROLLED = "ENROLLED", "Enrolled"
    PROMOTED = "PROMOTED", "Promoted"
    REPEATED = "REPEATED", "Repeated"
    TRANSFERRED = "TRANSFERRED", "Transferred"
    GRADUATED = "GRADUATED", "Graduated"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


class Enrollment(TenantModel):
    """A student's place in one academic session. Never deleted: its status records what happened."""

    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="enrollments")
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name="enrollments")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name="enrollments")
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="enrollments")
    roll_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ENROLLED)
    enrolled_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True)
    promoted_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="promoted_to")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="uniq_student_session_enrollment"),
            models.UniqueConstraint(fields=["session", "section", "roll_number"], condition=Q(roll_number__isnull=False), name="uniq_roll_in_section"),
        ]
        indexes = [
            models.Index(fields=["school", "section", "status"], name="enroll_school_section_idx"),
            models.Index(fields=["school", "student"], name="enroll_school_student_idx"),
        ]


class TimetableSlot(TenantModel):
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="timetable_slots")
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="timetable_slots")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="+")
    teacher = models.ForeignKey("teachers.Teacher", on_delete=models.CASCADE, related_name="timetable_slots")
    weekday = models.PositiveSmallIntegerField()  # 0 = Monday ... 6 = Sunday
    period_no = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=30, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "section", "weekday", "period_no"], name="uniq_slot_section_period"),
            models.UniqueConstraint(fields=["session", "teacher", "weekday", "period_no"], name="uniq_slot_teacher_period"),
            models.CheckConstraint(condition=Q(weekday__lte=6), name="timetable_weekday_valid"),
        ]
        ordering = ["weekday", "period_no"]
