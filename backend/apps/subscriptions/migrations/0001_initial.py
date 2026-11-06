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
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "monthly_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("currency", models.CharField(default="PKR", max_length=3)),
                ("max_students", models.PositiveIntegerField(blank=True, null=True)),
                ("max_teachers", models.PositiveIntegerField(blank=True, null=True)),
                ("max_classes", models.PositiveIntegerField(blank=True, null=True)),
                ("features", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("is_public", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("TRIALING", "Trialing"),
                            ("ACTIVE", "Active"),
                            ("PAST_DUE", "Past due"),
                            ("EXPIRED", "Expired"),
                            ("CANCELLED", "Cancelled"),
                            ("SUSPENDED", "Suspended"),
                        ],
                        default="TRIALING",
                        max_length=12,
                    ),
                ),
                ("trial_start", models.DateTimeField()),
                ("trial_end", models.DateTimeField()),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscriptions",
                        to="subscriptions.plan",
                    ),
                ),
                (
                    "school",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subscription",
                        to="tenants.school",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SubscriptionEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("event_type", models.CharField(max_length=30)),
                ("from_status", models.CharField(blank=True, max_length=12)),
                ("to_status", models.CharField(blank=True, max_length=12)),
                ("delta_days", models.IntegerField(blank=True, null=True)),
                ("reason", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "from_plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="subscriptions.plan",
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="tenants.school",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="subscriptions.subscription",
                    ),
                ),
                (
                    "to_plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="subscriptions.plan",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.CheckConstraint(
                condition=models.Q(("trial_end__gt", models.F("trial_start"))),
                name="subscription_trial_window_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["status", "end_date"], name="sub_status_end_idx"),
        ),
        migrations.AddIndex(
            model_name="subscription",
            index=models.Index(fields=["status", "trial_end"], name="sub_status_trial_idx"),
        ),
        migrations.AddIndex(
            model_name="subscriptionevent",
            index=models.Index(fields=["subscription", "created_at"], name="subevent_sub_created_idx"),
        ),
    ]
