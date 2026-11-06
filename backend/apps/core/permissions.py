"""Authorization building blocks.

Three layers on every tenant request:
  1. TenantAccess        - authenticated, belongs to a school, school is usable, password not expired
  2. HasRolePermission   - the role registry grants the permission this view/action requires (fail closed)
  3. Scope               - queryset restriction (tenant filter in TenantScopedViewSet; role scopes in later phases)
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .exceptions import PasswordChangeRequired, SchoolDisabled


class IsPlatformAdmin(BasePermission):
    """Platform (Super Admin) endpoints. Applied on the platform router base in Phase 3."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_platform_admin)


class TenantAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.school_id is None:
            raise PermissionDenied("This resource belongs to a school account.", code="tenant_required")
        if not user.school.is_accessible:
            raise SchoolDisabled()
        if user.must_change_password:
            raise PasswordChangeRequired()
        if getattr(view, "subscription_gate", True):
            from apps.subscriptions.access import enforce_subscription_access  # lazy: core must not import apps at load

            enforce_subscription_access(user.school, request.method)
        return True


def required_permission_for(view, request=None) -> str | None:
    """`permission_map` keys are viewset action names, or lower-case HTTP methods for plain APIViews."""
    mapping = getattr(view, "permission_map", None)
    if mapping is not None:
        key = getattr(view, "action", None)
        if key is None and request is not None:
            key = request.method.lower()
        return mapping.get(key)
    return getattr(view, "required_permission", None)


class HasRolePermission(BasePermission):
    """Looks up the permission code the view declares (`required_permission` or `permission_map[action]`).
    A view that declares nothing is denied."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        code = required_permission_for(view, request)
        if code is None:
            return False
        return user.can(code)
