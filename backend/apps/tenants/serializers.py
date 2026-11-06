from functools import cache
from zoneinfo import available_timezones

from rest_framework import serializers

from apps.core.validators import validate_phone_number

from .images import image_url
from .models import School


@cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


class SchoolProfileSerializer(serializers.ModelSerializer):
    logo = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)  # base64 data URL
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = ("id", "name", "slug", "status", "email", "phone", "country", "city", "address", "timezone", "currency", "logo", "logo_url")
        read_only_fields = ("id", "slug", "status", "currency")  # status: Super Admin only; currency: fixed once billing exists

    def get_logo_url(self, obj):
        return image_url(obj.logo_id)

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("School name is too short.")
        return value

    def validate_phone(self, value):
        return validate_phone_number(value)

    def validate_timezone(self, value):
        if value not in _timezones():
            raise serializers.ValidationError("Unknown timezone.")
        return value
