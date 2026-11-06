from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import DomainError

from ..models import User
from ..roles import SCHOOL_ROLES
from .auth import AuthService


class SchoolUserService:
    """School-admin management of the school's own users.

    Invariant: an admin cannot change their own role or deactivate themselves, and only admins manage users,
    so a school can never be left without an active School Admin.
    """

    ASSIGNABLE_ROLES = SCHOOL_ROLES

    @staticmethod
    @transaction.atomic
    def create(*, actor: User, data: dict, request) -> User:
        user = User.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data.get("last_name", ""),
            phone=data.get("phone", ""),
            role=data["role"],
            school=actor.school,  # tenant comes from the actor, never from input
            must_change_password=True,
        )
        AuditService.record(
            AuditAction.USER_CREATED, actor=actor, entity_type="user", entity_id=user.id,
            description=f"Created {user.role} {user.email}", request=request,
        )
        return user

    @staticmethod
    @transaction.atomic
    def update(*, actor: User, user: User, data: dict, request) -> User:
        if actor.id == user.id and (
            ("role" in data and data["role"] != user.role) or data.get("is_active") is False
        ):
            raise DomainError("You cannot change your own role or deactivate your own account.", code="cannot_modify_self")
        if "role" in data and data["role"] not in SchoolUserService.ASSIGNABLE_ROLES:
            raise ValidationError({"role": ["Invalid role."]})

        was_active = user.is_active
        for field in ("first_name", "last_name", "phone", "role", "is_active"):
            if field in data:
                setattr(user, field, data[field])
        user.save()

        if was_active and not user.is_active:
            AuthService.revoke_all_sessions(user)
            action = AuditAction.USER_DEACTIVATED
        elif not was_active and user.is_active:
            action = AuditAction.USER_REACTIVATED
        else:
            action = AuditAction.USER_UPDATED
        AuditService.record(
            action, actor=actor, entity_type="user", entity_id=user.id,
            description=f"Updated {user.email}", metadata={"fields": sorted(data.keys())}, request=request,
        )
        return user
