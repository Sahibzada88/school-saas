import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import UUIDTimestampedModel


class SubscriptionStatus(models.TextChoices):
    TRIALING = "TRIALING", "Trialing"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"
    SUSPENDED = "SUSPENDED", "Suspended"


class Plan(UUIDTimestampedModel):
    """Database-driven plan. NULL limits mean unlimited. No prices live in code."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="PKR")
    max_students = models.PositiveIntegerField(null=True, blank=True)
    max_teachers = models.PositiveIntegerField(null=True, blank=True)
    max_classes = models.PositiveIntegerField(null=True, blank=True)
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)  # inactive plans cannot be newly assigned
    is_public = models.BooleanField(default=True)  # shown by the public /plans/ endpoint
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Subscription(UUIDTimestampedModel):
    """One per school. `status` is the persisted/manual status; what a school can actually do right now is
    computed from the timestamps by state.effective_state() so nothing depends on a scheduler."""

    school = models.OneToOneField("tenants.School", on_delete=models.PROTECT, related_name="subscription")
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIALING)
    trial_start = models.DateTimeField()
    trial_end = models.DateTimeField()
    start_date = models.DateTimeField(null=True, blank=True)  # first activation (NULL = never paid)
    end_date = models.DateTimeField(null=True, blank=True)  # end of the paid period
    cancelled_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(trial_end__gt=F("trial_start")), name="subscription_trial_window_valid"),
        ]
        indexes = [
            models.Index(fields=["status", "end_date"], name="sub_status_end_idx"),
            models.Index(fields=["status", "trial_end"], name="sub_status_trial_idx"),
        ]


class SubscriptionEventType:
    TRIAL_STARTED = "TRIAL_STARTED"
    TRIAL_EXTENDED = "TRIAL_EXTENDED"
    ACTIVATED = "ACTIVATED"
    RENEWED = "RENEWED"
    EXTENDED = "EXTENDED"
    PLAN_CHANGED = "PLAN_CHANGED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"
    RESUMED = "RESUMED"
    STATE_CHANGED = "STATE_CHANGED"


class SubscriptionEvent(models.Model):
    """Append-only history of everything that happened to a subscription."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="events")
    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="+")
    event_type = models.CharField(max_length=30)
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12, blank=True)
    from_plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    to_plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    delta_days = models.IntegerField(null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["subscription", "created_at"], name="subevent_sub_created_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Subscription events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Subscription events cannot be deleted.")
