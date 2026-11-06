from datetime import date

from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.fields import TenantScopedRelatedField
from apps.core.validators import validate_phone_number
from apps.tenants.images import image_url

from .models import Guardian, Student, StudentDocument, StudentGuardian, StudentStatus


def _current_enrollment(student):
    cached = getattr(student, "current_enrollments", None)
    if cached is None:
        return None
    return cached[0] if cached else None


class GuardianSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    user = TenantScopedRelatedField(queryset=User.objects.filter(role=Role.PARENT), required=False, allow_null=True)

    class Meta:
        model = Guardian
        fields = ("id", "first_name", "last_name", "full_name", "phone", "email", "national_id", "occupation", "address", "user", "created_at")
        read_only_fields = ("id", "full_name", "created_at")

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_user(self, value):
        if value is not None:
            clash = Guardian.objects.filter(user=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError("This user is already linked to another guardian.")
        return value


class StudentGuardianSerializer(serializers.ModelSerializer):
    guardian = GuardianSerializer(read_only=True)

    class Meta:
        model = StudentGuardian
        fields = ("id", "guardian", "relationship", "is_primary", "is_emergency_contact")
        read_only_fields = fields


class LinkGuardianSerializer(serializers.Serializer):
    """Link an existing guardian (`guardian`) or create one inline (`new_guardian`), in one call."""

    guardian = TenantScopedRelatedField(queryset=Guardian.objects.all(), required=False)
    new_guardian = GuardianSerializer(required=False)
    relationship = serializers.ChoiceField(choices=StudentGuardian._meta.get_field("relationship").choices, default="GUARDIAN")
    is_primary = serializers.BooleanField(default=False)
    is_emergency_contact = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if bool(attrs.get("guardian")) == bool(attrs.get("new_guardian")):
            raise serializers.ValidationError("Provide either an existing guardian or the details of a new one.")
        return attrs


class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    photo_url = serializers.SerializerMethodField()
    current_class = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = (
            "id", "student_number", "first_name", "last_name", "full_name", "gender", "date_of_birth", "admission_date",
            "status", "phone", "photo_url", "current_class",
        )
        read_only_fields = fields

    def get_photo_url(self, obj):
        return image_url(obj.photo_id)

    def get_current_class(self, obj):
        enrollment = _current_enrollment(obj)
        if enrollment is None:
            return None
        return {
            "enrollment_id": str(enrollment.id), "class_id": str(enrollment.school_class_id), "class_name": enrollment.school_class.name,
            "section_id": str(enrollment.section_id), "section_name": enrollment.section.name, "roll_number": enrollment.roll_number,
        }


class StudentDetailSerializer(StudentListSerializer):
    guardians = StudentGuardianSerializer(source="guardian_links", many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta(StudentListSerializer.Meta):
        fields = StudentListSerializer.Meta.fields + (
            "email", "address", "blood_group", "notes", "status_changed_at", "user", "guardians", "created_at",
        )
        read_only_fields = fields


class StudentWriteSerializer(serializers.ModelSerializer):
    photo = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)  # base64 data URL
    user = TenantScopedRelatedField(queryset=User.objects.filter(role=Role.STUDENT), required=False, allow_null=True)

    class Meta:
        model = Student
        fields = (
            "first_name", "last_name", "date_of_birth", "gender", "blood_group", "phone", "email", "address",
            "admission_date", "notes", "photo", "user",
        )
        extra_kwargs = {"admission_date": {"required": False}}

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_date_of_birth(self, value):
        if value >= date.today():
            raise serializers.ValidationError("Date of birth must be in the past.")
        if value.year < 1990:
            raise serializers.ValidationError("Check the date of birth.")
        return value

    def validate_user(self, value):
        if value is not None:
            clash = Student.all_objects.filter(user=value)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError("This user is already linked to another student.")
        return value


class StatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=StudentStatus.choices)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class StudentDocumentSerializer(serializers.ModelSerializer):
    student = TenantScopedRelatedField(queryset=Student.objects.all())

    class Meta:
        model = StudentDocument
        fields = ("id", "student", "doc_type", "title", "received_on", "notes", "created_at")
        read_only_fields = ("id", "created_at")
