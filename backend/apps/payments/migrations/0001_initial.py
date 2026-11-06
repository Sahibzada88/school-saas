import uuid
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenants", "0002_school_status_changed_by"),
        ("subscriptions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("currency", models.CharField(max_length=3)),
                (
                    "payment_method",
                    models.CharField(
                        choices=[
                            ("BANK_TRANSFER", "Bank transfer"),
                            ("JAZZCASH", "JazzCash"),
                            ("EASYPAISA", "Easypaisa"),
                            ("CASH", "Cash"),
                            ("OTHER", "Other"),
                        ],
                        max_length=20,
                    ),
                ),
                ("transaction_reference", models.CharField(blank=True, max_length=100)),
                ("payment_date", models.DateField()),
                ("months", models.PositiveSmallIntegerField(default=1)),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("notes", models.TextField(blank=True)),
                ("gateway", models.CharField(default="MANUAL", max_length=20)),
                ("gateway_payload", models.JSONField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platform_payments",
                        to="tenants.school",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payments",
                        to="subscriptions.subscription",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="platformpayment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("transaction_reference", ""), _negated=True),
                fields=("payment_method", "transaction_reference"),
                name="uniq_payment_method_reference",
            ),
        ),
        migrations.AddConstraint(
            model_name="platformpayment",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)), name="platform_payment_amount_positive"
            ),
        ),
        migrations.AddIndex(
            model_name="platformpayment",
            index=models.Index(fields=["school", "payment_date"], name="payment_school_date_idx"),
        ),
        migrations.AddIndex(
            model_name="platformpayment",
            index=models.Index(fields=["payment_date"], name="payment_date_idx"),
        ),
    ]
