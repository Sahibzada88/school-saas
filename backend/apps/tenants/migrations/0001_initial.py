import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Active"), ("SUSPENDED", "Suspended"), ("INACTIVE", "Inactive")],
                        default="ACTIVE",
                        max_length=12,
                    ),
                ),
                ("status_reason", models.TextField(blank=True)),
                ("status_changed_at", models.DateTimeField(blank=True, null=True)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("country", models.CharField(max_length=100)),
                ("city", models.CharField(max_length=100)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("timezone", models.CharField(default="Asia/Karachi", max_length=64)),
                ("currency", models.CharField(default="PKR", max_length=3)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="SchoolSettings",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student_number_prefix", models.CharField(default="STU", max_length=10)),
                ("invoice_prefix", models.CharField(default="INV", max_length=10)),
                ("receipt_prefix", models.CharField(default="RCT", max_length=10)),
                ("week_start", models.PositiveSmallIntegerField(default=1)),
                ("extra", models.JSONField(blank=True, default=dict)),
                (
                    "school",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settings",
                        to="tenants.school",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="school",
            index=models.Index(fields=["status"], name="school_status_idx"),
        ),
        migrations.AddIndex(
            model_name="school",
            index=models.Index(fields=["created_at"], name="school_created_idx"),
        ),
    ]
