from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TenantModel, TenantSoftDeleteModel


class GradingScale(TenantModel):
    name = models.CharField(max_length=60)
    is_default = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="uniq_grading_scale_name")]


class GradeBand(TenantModel):
    scale = models.ForeignKey(GradingScale, on_delete=models.CASCADE, related_name="bands")
    grade = models.CharField(max_length=5)
    min_percent = models.DecimalField(max_digits=5, decimal_places=2)
    max_percent = models.DecimalField(max_digits=5, decimal_places=2)
    gpa_points = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    remark = models.CharField(max_length=60, blank=True)
    is_pass = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(min_percent__lte=F("max_percent")), name="grade_band_range_valid")]
        ordering = ["-min_percent"]


class ExamType(TenantSoftDeleteModel):
    name = models.CharField(max_length=60)
    weightage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["school", "name"], condition=Q(is_deleted=False), name="uniq_exam_type_active")]


class ExamStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SCHEDULED = "SCHEDULED", "Scheduled"
    MARKS_ENTRY = "MARKS_ENTRY", "Marks entry"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class Exam(TenantSoftDeleteModel):
    session = models.ForeignKey("academics.AcademicSession", on_delete=models.PROTECT, related_name="exams")
    exam_type = models.ForeignKey(ExamType, on_delete=models.PROTECT, related_name="exams")
    name = models.CharField(max_length=120)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    grading_scale = models.ForeignKey(GradingScale, on_delete=models.PROTECT, related_name="exams")
    status = models.CharField(max_length=12, choices=ExamStatus.choices, default=ExamStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["school", "session", "status"], name="exam_school_session_idx")]


class ExamSubject(TenantModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="subjects")
    school_class = models.ForeignKey("academics.SchoolClass", on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="+")
    exam_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "school_class", "subject"], name="uniq_exam_subject"),
            models.CheckConstraint(condition=Q(passing_marks__lte=F("total_marks")), name="exam_subject_passing_valid"),
        ]


class Mark(TenantModel):
    exam_subject = models.ForeignKey(ExamSubject, on_delete=models.CASCADE, related_name="marks")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT, related_name="marks")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="marks")
    obtained_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_absent = models.BooleanField(default=False)
    remarks = models.CharField(max_length=200, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam_subject", "student"], name="uniq_mark_per_subject_student"),
            models.CheckConstraint(condition=Q(obtained_marks__isnull=True) | Q(obtained_marks__gte=0), name="mark_non_negative"),
        ]
        indexes = [models.Index(fields=["school", "student"], name="mark_school_student_idx")]


class ResultStatus(models.TextChoices):
    PASS = "PASS", "Pass"
    FAIL = "FAIL", "Fail"


class ReportCard(TenantModel):
    """Snapshot written on publish, so later changes to grading never rewrite history."""

    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="report_cards")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="report_cards")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT, related_name="report_cards")
    total_marks = models.DecimalField(max_digits=8, decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5, blank=True)
    gpa = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    position_section = models.PositiveIntegerField(null=True, blank=True)
    position_class = models.PositiveIntegerField(null=True, blank=True)
    result_status = models.CharField(max_length=4, choices=ResultStatus.choices)
    breakdown = models.JSONField(default=dict)
    teacher_remarks = models.CharField(max_length=300, blank=True)
    principal_remarks = models.CharField(max_length=300, blank=True)
    computed_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["exam", "student"], name="uniq_report_card")]
        indexes = [
            models.Index(fields=["school", "exam"], name="rc_school_exam_idx"),
            models.Index(fields=["school", "student"], name="rc_school_student_idx"),
        ]
