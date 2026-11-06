import uuid

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
            name="Notification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("TRIAL_STARTED", "Trial started"),
                            ("TRIAL_EXPIRING", "Trial expiring"),
                            ("TRIAL_EXPIRED", "Trial expired"),
                            ("SUBSCRIPTION_ACTIVATED", "Subscription activated"),
                            ("SUBSCRIPTION_EXPIRING", "Subscription expiring"),
                            ("SUBSCRIPTION_EXPIRED", "Subscription expired"),
                            ("PAYMENT_RECEIVED", "Payment received"),
                            ("SUBSCRIPTION_EXTENDED", "Subscription extended"),
                            ("SCHOOL_ACTIVATED", "School activated"),
                            ("SCHOOL_SUSPENDED", "School suspended"),
                            ("SCHOOL_DEACTIVATED", "School deactivated"),
                            ("SCHOOL_REACTIVATED", "School reactivated"),
                            ("ANNOUNCEMENT", "Announcement"),
                        ],
                        max_length=30,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField(blank=True)),
                (
                    "severity",
                    models.CharField(
                        choices=[("INFO", "Info"), ("WARNING", "Warning"), ("CRITICAL", "Critical")],
                        default="INFO",
                        max_length=10,
                    ),
                ),
                ("data", models.JSONField(blank=True, default=dict)),
                ("dedupe_key", models.CharField(blank=True, max_length=200, null=True)),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "school",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="tenants.school",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=models.Q(("dedupe_key__isnull", False)),
                fields=("recipient", "dedupe_key"),
                name="uniq_notification_dedupe",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["recipient", "is_read", "created_at"], name="notif_recipient_idx"),
        ),
    ]
