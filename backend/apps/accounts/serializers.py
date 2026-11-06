from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.validators import validate_phone_number

from .models import User
from .roles import ROLE_PERMISSIONS, SCHOOL_ROLES

def serialize_me(user: User) -> dict:
    """Payload of /auth/me, login, register, refresh. `permissions` is the single source for the frontend."""
    from apps.subscriptions.services import SubscriptionService  # lazy: avoids an import cycle at load time

    school = user.school if user.school_id else None
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "role": user.role,
            "must_change_password": user.must_change_password,
        },
        "school": (
            {
                "id": str(school.id),
                "name": school.name,
                "slug": school.slug,
                "status": school.status,
                "status_reason": school.status_reason,
            }
            if school
            else None
        ),
        "subscription": SubscriptionService.summary(school) if school else None,
        "permissions": sorted(ROLE_PERMISSIONS.get(user.role, frozenset())),
    }


def _validate_new_password(value: str, user: User | None = None) -> str:
    try:
        validate_password(value, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


def _validate_phone(value: str) -> str:
    return validate_phone_number(value)


def _unique_email(value: str) -> str:
    email = value.strip().lower()
    if User.objects.filter(email=email).exists():
        raise serializers.ValidationError("An account with this email already exists.")
    return email


class RegisterSerializer(serializers.Serializer):
    school_name = serializers.CharField(max_length=200)
    admin_name = serializers.CharField(max_length=200)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    country = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)

    def validate_school_name(self, value):
        return value.strip()

    def validate_email(self, value):
        return _unique_email(value)

    def validate_phone(self, value):
        return _validate_phone(value)

    def validate(self, attrs):
        first, _, last = attrs["admin_name"].strip().partition(" ")
        probe = User(email=attrs["email"], first_name=first, last_name=last.strip())
        try:
            validate_password(attrs["password"], user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, max_length=128)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, max_length=128)
    new_password = serializers.CharField(trim_whitespace=False, max_length=128)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    new_password = serializers.CharField(trim_whitespace=False, max_length=128)


# ----------------------------------------------------------------------- school user management
class SchoolUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "phone", "role", "is_active", "must_change_password", "last_login", "created_at")
        read_only_fields = fields


class SchoolUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=SCHOOL_ROLES)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_email(self, value):
        return _unique_email(value)

    def validate_phone(self, value):
        return _validate_phone(value)

    def validate(self, attrs):
        probe = User(email=attrs["email"], first_name=attrs["first_name"], last_name=attrs.get("last_name", ""))
        try:
            validate_password(attrs["password"], user=probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs


class SchoolUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=SCHOOL_ROLES, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_phone(self, value):
        return _validate_phone(value)
