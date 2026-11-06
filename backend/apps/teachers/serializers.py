from datetime import date

from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.fields import TenantScopedRelatedField
from apps.core.validators import validate_phone_number
from apps.tenants.images import image_url

from .models import Teacher


class TeacherListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Teacher
        fields = ("id", "employee_id", "first_name", "last_name", "full_name", "gender", "phone", "email", "qualification", "joining_date", "status", "photo_url")
        read_only_fields = fields

    def get_photo_url(self, obj):
        return image_url(obj.photo_id)


class TeacherDetailSerializer(TeacherListSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    assignments = serializers.SerializerMethodField()

    class Meta(TeacherListSerializer.Meta):
        fields = TeacherListSerializer.Meta.fields + ("date_of_birth", "address", "user", "assignments", "created_at")
        read_only_fields = fields

    def get_assignments(self, obj):
        rows = obj.assignments.filter(session__is_current=True).select_related("section__school_class", "subject")
        return [
            {"id": str(a.id), "section_id": str(a.section_id), "section": f"{a.section.school_class.name}-{a.section.name}",
             "subject": a.subject.name if a.subject_id else None, "is_class_teacher": a.is_class_teacher}
            for a in rows
        ]


class TeacherWriteSerializer(serializers.ModelSerializer):
    photo = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)
    user = TenantScopedRelatedField(queryset=User.objects.filter(role=Role.TEACHER), required=False, allow_null=True)

    class Meta:
        model = Teacher
        fields = ("first_name", "last_name", "gender", "date_of_birth", "phone", "email", "address", "qualification", "joining_date", "status", "photo", "user")
        extra_kwargs = {"joining_date": {"required": False}}

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_date_of_birth(self, value):
        if value and value >= date.today():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return value

    def validate_user(self, value):
        if value is not None:
            clash = Teacher.all_objects.filter(user=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError("This user is already linked to another teacher.")
        return value
