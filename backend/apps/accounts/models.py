import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import UUIDTimestampedModel

from .roles import ROLE_PERMISSIONS, Role


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", Role.SCHOOL_ADMIN)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        """Platform-level Super Admin (no school). Used by `manage.py createsuperuser`."""
        extra["role"] = Role.SUPER_ADMIN
        extra["school"] = None
        return self._create(email, password, **extra)


class User(AbstractBaseUser, UUIDTimestampedModel):
    email = models.EmailField(max_length=254, unique=True)  # always stored lowercase
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    school = models.ForeignKey(
        "tenants.School", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci"),
            models.CheckConstraint(
                condition=(
                    Q(role="SUPER_ADMIN", school__isnull=True)
                    | (~Q(role="SUPER_ADMIN") & Q(school__isnull=False))
                ),
                name="user_super_admin_xor_school",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "role"], name="user_school_role_idx"),
            models.Index(fields=["school", "is_active"], name="user_school_active_idx"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def is_platform_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def can(self, permission_code: str) -> bool:
        return permission_code in ROLE_PERMISSIONS.get(self.role, frozenset())


class AuthSession(UUIDTimestampedModel):
    """One row per issued refresh token. Rotation creates a new row in the same family;
    presenting an already-rotated token revokes the whole family (theft detection)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_sessions")
    family_id = models.UUIDField(db_index=True)
    refresh_jti = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_at"], name="session_user_revoked_idx")]


class PasswordResetToken(UUIDTimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class AttemptScope(models.TextChoices):
    LOGIN = "LOGIN", "Login"
    REGISTER = "REGISTER", "Register"
    PASSWORD_RESET = "PASSWORD_RESET", "Password reset"


class LoginAttempt(models.Model):
    """Append-only throttle ledger. DB-backed because serverless instances share no memory."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=16, choices=AttemptScope.choices)
    email_norm = models.CharField(max_length=254, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    succeeded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["scope", "email_norm", "created_at"], name="attempt_email_idx"),
            models.Index(fields=["scope", "ip", "created_at"], name="attempt_ip_idx"),
            models.Index(fields=["created_at"], name="attempt_created_idx"),
        ]
