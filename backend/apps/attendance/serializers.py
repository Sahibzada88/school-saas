from rest_framework import serializers

from apps.academics.models import Section
from apps.core.fields import TenantScopedRelatedField

from .models import AttendanceStatus, StudentAttendance, TeacherAttendance


class StudentMarkSerializer(serializers.Serializer):
    student = serializers.UUIDField()
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    remarks = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class MarkStudentsSerializer(serializers.Serializer):
    section = TenantScopedRelatedField(queryset=Section.objects.all())
    date = serializers.DateField()
    records = StudentMarkSerializer(many=True, allow_empty=False)


class TeacherMarkSerializer(serializers.Serializer):
    teacher = serializers.UUIDField()
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    check_in = serializers.TimeField(required=False, allow_null=True)
    check_out = serializers.TimeField(required=False, allow_null=True)
    remarks = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class MarkTeachersSerializer(serializers.Serializer):
    date = serializers.DateField()
    records = TeacherMarkSerializer(many=True, allow_empty=False)


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    section_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentAttendance
        fields = ("id", "student", "student_name", "section", "section_name", "date", "status", "remarks")
        read_only_fields = fields

    def get_section_name(self, obj):
        return f"{obj.section.school_class.name}-{obj.section.name}"


class TeacherAttendanceSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)

    class Meta:
        model = TeacherAttendance
        fields = ("id", "teacher", "teacher_name", "date", "status", "check_in", "check_out", "remarks")
        read_only_fields = fields
