from rest_framework import serializers

from apps.core.fields import TenantScopedRelatedField
from apps.students.models import Student
from apps.teachers.models import Teacher

from .models import (
    AcademicSession,
    ClassSubject,
    Enrollment,
    Section,
    SchoolClass,
    Subject,
    TeacherAssignment,
    TimetableSlot,
)


class AcademicSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicSession
        fields = ("id", "name", "start_date", "end_date", "is_current")
        read_only_fields = ("id",)

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": ["End date must be after the start date."]})
        return attrs


class SchoolClassSerializer(serializers.ModelSerializer):
    section_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SchoolClass
        fields = ("id", "name", "level_order", "section_count")
        read_only_fields = ("id", "section_count")


class SectionSerializer(serializers.ModelSerializer):
    school_class = TenantScopedRelatedField(queryset=SchoolClass.objects.all())
    class_teacher = TenantScopedRelatedField(queryset=Teacher.objects.all(), required=False, allow_null=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    class_teacher_name = serializers.SerializerMethodField()
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Section
        fields = ("id", "school_class", "class_name", "name", "capacity", "class_teacher", "class_teacher_name", "student_count")
        read_only_fields = ("id", "class_name", "class_teacher_name", "student_count")

    def get_class_teacher_name(self, obj):
        return obj.class_teacher.full_name if obj.class_teacher_id else None


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ("id", "name", "code")
        read_only_fields = ("id",)

    def validate_code(self, value):
        return value.strip().upper()


class ClassSubjectSerializer(serializers.ModelSerializer):
    school_class = TenantScopedRelatedField(queryset=SchoolClass.objects.all())
    subject = TenantScopedRelatedField(queryset=Subject.objects.all())
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ClassSubject
        fields = ("id", "school_class", "class_name", "subject", "subject_name", "is_optional")
        read_only_fields = ("id", "class_name", "subject_name")


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    teacher = TenantScopedRelatedField(queryset=Teacher.objects.all())
    section = TenantScopedRelatedField(queryset=Section.objects.all())
    subject = TenantScopedRelatedField(queryset=Subject.objects.all(), required=False, allow_null=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    section_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()

    class Meta:
        model = TeacherAssignment
        fields = ("id", "session", "teacher", "teacher_name", "section", "section_name", "subject", "subject_name", "is_class_teacher")
        read_only_fields = ("id", "teacher_name", "section_name", "subject_name")

    def get_section_name(self, obj):
        return f"{obj.section.school_class.name}-{obj.section.name}"

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject_id else None


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    session_name = serializers.CharField(source="session.name", read_only=True)

    class Meta:
        model = Enrollment
        fields = (
            "id", "student", "student_name", "student_number", "session", "session_name", "school_class", "class_name",
            "section", "section_name", "roll_number", "status", "enrolled_on", "ended_on",
        )
        read_only_fields = fields


class EnrollInputSerializer(serializers.Serializer):
    student = TenantScopedRelatedField(queryset=Student.objects.all())
    session = TenantScopedRelatedField(queryset=AcademicSession.objects.all(), required=False)
    section = TenantScopedRelatedField(queryset=Section.objects.all())
    roll_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class EnrollmentUpdateSerializer(serializers.Serializer):
    section = TenantScopedRelatedField(queryset=Section.objects.all(), required=False)
    roll_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class PromotionDecisionSerializer(serializers.Serializer):
    enrollment = TenantScopedRelatedField(queryset=Enrollment.objects.all())
    outcome = serializers.ChoiceField(choices=["PROMOTE", "REPEAT", "GRADUATE"])


class PromoteSerializer(serializers.Serializer):
    from_session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    to_session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    promote_to = TenantScopedRelatedField(queryset=Section.objects.all(), required=False)
    repeat_to = TenantScopedRelatedField(queryset=Section.objects.all(), required=False)
    decisions = PromotionDecisionSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["from_session"].id == attrs["to_session"].id:
            raise serializers.ValidationError({"to_session": ["Choose a different session to promote into."]})
        outcomes = {d["outcome"] for d in attrs["decisions"]}
        if "PROMOTE" in outcomes and "promote_to" not in attrs:
            raise serializers.ValidationError({"promote_to": ["Choose the section promoted students go to."]})
        if "REPEAT" in outcomes and "repeat_to" not in attrs:
            raise serializers.ValidationError({"repeat_to": ["Choose the section repeating students go to."]})
        return attrs


class TimetableSlotSerializer(serializers.ModelSerializer):
    session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    section = TenantScopedRelatedField(queryset=Section.objects.all())
    subject = TenantScopedRelatedField(queryset=Subject.objects.all())
    teacher = TenantScopedRelatedField(queryset=Teacher.objects.all())
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    section_name = serializers.SerializerMethodField()

    class Meta:
        model = TimetableSlot
        fields = ("id", "session", "section", "section_name", "subject", "subject_name", "teacher", "teacher_name", "weekday", "period_no", "start_time", "end_time", "room")
        read_only_fields = ("id", "subject_name", "teacher_name", "section_name")

    def get_section_name(self, obj):
        return f"{obj.section.school_class.name}-{obj.section.name}"

    def validate_weekday(self, value):
        if value > 6:
            raise serializers.ValidationError("Weekday must be 0 (Monday) to 6 (Sunday).")
        return value

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": ["End time must be after the start time."]})
        return attrs
