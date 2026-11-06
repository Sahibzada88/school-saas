import re

from rest_framework import serializers

_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")


def validate_phone_number(value: str) -> str:
    if value and not _PHONE_RE.match(value):
        raise serializers.ValidationError("Enter a valid phone number.")
    return value
