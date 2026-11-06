import uuid

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

import apps.accounts.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(blank=True, max_length=100)),
                ("phone", models.CharField(blank=True, max_length=30)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("SUPER_ADMIN", "Super Admin"),
                            ("SCHOOL_ADMIN", "School Admin"),
                            ("TEACHER", "Teacher"),
                            ("ACCOUNTANT", "Accountant"),
                            ("RECEPTIONIST", "Receptionist"),
                            ("PARENT", "Parent"),
                            ("STUDENT", "Student"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("must_change_password", models.BooleanField(default=False)),
                (
                    "school",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="users",
                        to="tenants.school",
                    ),
                ),
            ],
            options={"abstract": False},
            managers=[("objects", apps.accounts.models.UserManager())],
        ),
        migrations.CreateModel(
            name="AuthSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("family_id", models.UUIDField(db_index=True)),
                ("refresh_jti", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_sessions",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PasswordResetToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_reset_tokens",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "scope",
                    models.CharField(
                        choices=[("LOGIN", "Login"), ("REGISTER", "Register"), ("PASSWORD_RESET", "Password reset")],
                        max_length=16,
                    ),
                ),
                ("email_norm", models.CharField(blank=True, max_length=254)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("succeeded", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("email"), name="uniq_user_email_ci"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(role="SUPER_ADMIN", school__isnull=True)
                    | (~models.Q(role="SUPER_ADMIN") & models.Q(school__isnull=False))
                ),
                name="user_super_admin_xor_school",
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["school", "role"], name="user_school_role_idx"),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["school", "is_active"], name="user_school_active_idx"),
        ),
        migrations.AddIndex(
            model_name="authsession",
            index=models.Index(fields=["user", "revoked_at"], name="session_user_revoked_idx"),
        ),
        migrations.AddIndex(
            model_name="loginattempt",
            index=models.Index(fields=["scope", "email_norm", "created_at"], name="attempt_email_idx"),
        ),
        migrations.AddIndex(
            model_name="loginattempt",
            index=models.Index(fields=["scope", "ip", "created_at"], name="attempt_ip_idx"),
        ),
        migrations.AddIndex(
            model_name="loginattempt",
            index=models.Index(fields=["created_at"], name="attempt_created_idx"),
        ),
    ]
