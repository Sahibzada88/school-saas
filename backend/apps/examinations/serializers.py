from rest_framework import serializers

from apps.academics.models import AcademicSession, SchoolClass, Subject
from apps.core.fields import TenantScopedRelatedField

from .models import Exam, ExamSubject, ExamType, GradeBand, GradingScale, ReportCard


class GradeBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeBand
        fields = ("grade", "min_percent", "max_percent", "gpa_points", "remark", "is_pass")


class GradingScaleSerializer(serializers.ModelSerializer):
    bands = GradeBandSerializer(many=True, required=False)

    class Meta:
        model = GradingScale
        fields = ("id", "name", "is_default", "bands")
        read_only_fields = ("id",)


class ExamTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamType
        fields = ("id", "name", "weightage")
        read_only_fields = ("id",)


class ExamSerializer(serializers.ModelSerializer):
    session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    exam_type = TenantScopedRelatedField(queryset=ExamType.objects.all())
    grading_scale = TenantScopedRelatedField(queryset=GradingScale.objects.all(), required=False)
    session_name = serializers.CharField(source="session.name", read_only=True)
    exam_type_name = serializers.CharField(source="exam_type.name", read_only=True)
    subject_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Exam
        fields = ("id", "name", "session", "session_name", "exam_type", "exam_type_name", "grading_scale", "start_date", "end_date", "status", "published_at", "subject_count")
        read_only_fields = ("id", "status", "published_at", "session_name", "exam_type_name", "subject_count")

    def validate(self, attrs):
        start, end = attrs.get("start_date"), attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": ["End date cannot be before the start date."]})
        return attrs


class ExamSubjectSerializer(serializers.ModelSerializer):
    exam = TenantScopedRelatedField(queryset=Exam.objects.all())
    school_class = TenantScopedRelatedField(queryset=SchoolClass.objects.all())
    subject = TenantScopedRelatedField(queryset=Subject.objects.all())
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ExamSubject
        fields = ("id", "exam", "school_class", "class_name", "subject", "subject_name", "exam_date", "start_time", "duration_minutes", "total_marks", "passing_marks")
        read_only_fields = ("id", "class_name", "subject_name")

    def validate(self, attrs):
        total = attrs.get("total_marks", getattr(self.instance, "total_marks", None))
        passing = attrs.get("passing_marks", getattr(self.instance, "passing_marks", None))
        if total is not None and total <= 0:
            raise serializers.ValidationError({"total_marks": ["Total marks must be above zero."]})
        if total is not None and passing is not None and (passing < 0 or passing > total):
            raise serializers.ValidationError({"passing_marks": ["Passing marks must be between 0 and the total."]})
        return attrs


class MarkEntrySerializer(serializers.Serializer):
    student = serializers.UUIDField()
    obtained_marks = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(default=False)
    remarks = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class SaveMarksSerializer(serializers.Serializer):
    exam_subject = TenantScopedRelatedField(queryset=ExamSubject.objects.select_related("exam", "subject", "school_class"))
    entries = MarkEntrySerializer(many=True, allow_empty=False)


class RemarksSerializer(serializers.Serializer):
    teacher_remarks = serializers.CharField(max_length=300, required=False, allow_blank=True)
    principal_remarks = serializers.CharField(max_length=300, required=False, allow_blank=True)


class PublishSerializer(serializers.Serializer):
    force = serializers.BooleanField(default=False)


class ReportCardListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    class_name = serializers.CharField(source="enrollment.school_class.name", read_only=True)
    section_name = serializers.CharField(source="enrollment.section.name", read_only=True)

    class Meta:
        model = ReportCard
        fields = (
            "id", "exam", "exam_name", "student", "student_name", "student_number", "class_name", "section_name",
            "total_marks", "obtained_marks", "percentage", "grade", "gpa", "position_section", "position_class", "result_status",
        )
        read_only_fields = fields


class ReportCardDetailSerializer(ReportCardListSerializer):
    session_name = serializers.CharField(source="exam.session.name", read_only=True)
    roll_number = serializers.IntegerField(source="enrollment.roll_number", read_only=True)
    school_name = serializers.CharField(source="school.name", read_only=True)

    class Meta(ReportCardListSerializer.Meta):
        fields = ReportCardListSerializer.Meta.fields + (
            "session_name", "roll_number", "school_name", "breakdown", "teacher_remarks", "principal_remarks", "published_at",
        )
        read_only_fields = fields
