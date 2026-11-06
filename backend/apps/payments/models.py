from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import UUIDTimestampedModel


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "BANK_TRANSFER", "Bank transfer"
    JAZZCASH = "JAZZCASH", "JazzCash"
    EASYPAISA = "EASYPAISA", "Easypaisa"
    CASH = "CASH", "Cash"
    OTHER = "OTHER", "Other"


class PlatformPayment(UUIDTimestampedModel):
    """SaaS subscription payment recorded by a Super Admin. Completely separate from student fee payments (Phase 9).
    Never edited or deleted. `gateway`/`gateway_payload` are the hook for a future payment gateway."""

    school = models.ForeignKey("tenants.School", on_delete=models.PROTECT, related_name="platform_payments")
    subscription = models.ForeignKey("subscriptions.Subscription", on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    currency = models.CharField(max_length=3)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    transaction_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField()
    months = models.PositiveSmallIntegerField(default=1)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    gateway = models.CharField(max_length=20, default="MANUAL")
    gateway_payload = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["payment_method", "transaction_reference"],
                condition=~Q(transaction_reference=""),
                name="uniq_payment_method_reference",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="platform_payment_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["school", "payment_date"], name="payment_school_date_idx"),
            models.Index(fields=["payment_date"], name="payment_date_idx"),
        ]
