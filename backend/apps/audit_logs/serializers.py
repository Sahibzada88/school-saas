from rest_framework import serializers

from apps.accounts.roles import Role

from .models import AuditLog


class SchoolAuditLogSerializer(serializers.ModelSerializer):
    """What a School Admin sees: no IP, no raw metadata, and platform staff are shown generically."""

    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "created_at", "action", "description", "entity_type", "entity_id", "actor_name")
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        if obj.actor_role == Role.SUPER_ADMIN:
            return "Platform administration"
        return obj.actor.full_name if obj.actor_id else "System"


class PlatformAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_email = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id", "created_at", "action", "description", "entity_type", "entity_id",
            "actor_id", "actor_name", "actor_email", "actor_role",
            "school_id", "school_name", "ip", "metadata",
        )
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.full_name if obj.actor_id else None

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor_id else None

    def get_school_name(self, obj):
        return obj.school.name if obj.school_id else None
