from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.payments.models import PaymentMethod, PlatformPayment
from apps.subscriptions.models import Plan, Subscription
from apps.subscriptions.state import effective_state, summarize
from apps.tenants.models import School

from .config import PlatformConfig


def subscription_payload(sub: Subscription, now, cfg) -> dict:
    data = summarize(sub, effective_state(sub, now, cfg))
    data.update(
        id=str(sub.id), status=sub.status, trial_start=sub.trial_start, trial_end=sub.trial_end,
        start_date=sub.start_date, end_date=sub.end_date, cancelled_at=sub.cancelled_at, suspended_at=sub.suspended_at,
    )
    return data


def _school_subscription(school: School, context: dict):
    try:
        sub = school.subscription
    except ObjectDoesNotExist:
        return None
    return subscription_payload(sub, context.get("now") or timezone.now(), context.get("cfg") or PlatformConfig.defaults())


class PlatformSchoolListSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    admin_email = serializers.CharField(read_only=True, allow_null=True)
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = (
            "id", "name", "slug", "status", "email", "city", "country", "created_at",
            "user_count", "admin_email", "subscription",
        )
        read_only_fields = fields

    def get_subscription(self, obj):
        return _school_subscription(obj, self.context)


class PlatformSchoolDetailSerializer(PlatformSchoolListSerializer):
    active_user_count = serializers.IntegerField(read_only=True)
    status_changed_by_name = serializers.SerializerMethodField()
    admin = serializers.SerializerMethodField()

    class Meta(PlatformSchoolListSerializer.Meta):
        fields = PlatformSchoolListSerializer.Meta.fields + (
            "phone", "address", "timezone", "currency", "status_reason", "status_changed_at",
            "status_changed_by_name", "active_user_count", "admin",
        )
        read_only_fields = fields

    def get_status_changed_by_name(self, obj):
        return obj.status_changed_by.full_name if obj.status_changed_by_id else None

    def get_admin(self, obj):
        admin = User.objects.filter(school=obj, role=Role.SCHOOL_ADMIN).order_by("created_at").first()
        if admin is None:
            return None
        return {"name": admin.full_name, "email": admin.email, "phone": admin.phone}


class LifecycleSerializer(serializers.Serializer):
    """Body of suspend / deactivate / reactivate. `confirm` is the server-side twin of the UI confirmation dialog."""

    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Confirmation is required.")
        return value

    def validate(self, attrs):
        attrs["reason"] = attrs["reason"].strip()
        if self.context.get("require_reason") and len(attrs["reason"]) < 3:
            raise serializers.ValidationError({"reason": ["A reason of at least 3 characters is required."]})
        return attrs


class NotifySerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    body = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    severity = serializers.ChoiceField(choices=["INFO", "WARNING", "CRITICAL"], default="INFO")


# ----------------------------------------------------------------------- plans
class PlanSerializer(serializers.ModelSerializer):
    subscriber_count = serializers.IntegerField(read_only=True)
    features = serializers.ListField(child=serializers.CharField(max_length=100), max_length=20, required=False)

    class Meta:
        model = Plan
        fields = (
            "id", "name", "slug", "description", "monthly_price", "currency", "max_students", "max_teachers",
            "max_classes", "features", "is_active", "is_public", "sort_order", "subscriber_count", "created_at",
        )
        read_only_fields = ("id", "subscriber_count", "created_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:  # the slug is referenced by platform settings, so it is fixed after creation
            self.fields["slug"].read_only = True

    def validate_currency(self, value):
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Use a 3-letter currency code.")
        return value

    def validate_name(self, value):
        return value.strip()


# ----------------------------------------------------------------------- subscriptions
class DaysReasonSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365)
    reason = serializers.CharField(min_length=3, max_length=500)


class ChangePlanSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ReasonConfirmSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Confirmation is required.")
        return value


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class PlatformSubscriptionSerializer(serializers.Serializer):
    """Read-only; computed with the shared state engine."""

    def to_representation(self, sub):
        data = subscription_payload(sub, self.context["now"], self.context["cfg"])
        data["school"] = {"id": str(sub.school_id), "name": sub.school.name, "status": sub.school.status}
        return data


# ----------------------------------------------------------------------- payments
class PaymentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PlatformPayment
        fields = (
            "id", "school_id", "school_name", "subscription_id", "amount", "currency", "payment_method",
            "transaction_reference", "payment_date", "months", "period_start", "period_end", "notes",
            "created_by_name", "created_at",
        )
        read_only_fields = fields

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by_id else None


class RecordPaymentSerializer(serializers.Serializer):
    school = serializers.PrimaryKeyRelatedField(queryset=School.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.CharField(min_length=3, max_length=3, required=False)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    transaction_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    payment_date = serializers.DateField(required=False)
    months = serializers.IntegerField(min_value=1, max_value=36, default=1)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all(), required=False, allow_null=True, default=None)

    def validate_currency(self, value):
        return value.upper()

    def validate_transaction_reference(self, value):
        return value.strip()

    def validate_payment_date(self, value):
        if value > timezone.now().date() + timedelta(days=1):
            raise serializers.ValidationError("The payment date cannot be in the future.")
        return value

    def validate(self, attrs):
        attrs.setdefault("payment_date", timezone.now().date())
        sub = getattr(attrs["school"], "subscription", None)
        plan = attrs.get("plan") or (sub.plan if sub else None)
        attrs.setdefault("currency", plan.currency if plan else attrs["school"].currency)
        attrs["currency"] = attrs["currency"].upper()
        return attrs
