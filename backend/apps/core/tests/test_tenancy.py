from types import SimpleNamespace

from django.apps import apps
import config.urls  # noqa: F401  (imports every routed viewset so the registry is populated)
from django.test import SimpleTestCase, TestCase

from apps.accounts.models import User
from apps.core.managers import TenantQuerySet
from apps.core.models import TenantModel
from apps.core.permissions import HasRolePermission, IsPlatformAdmin, TenantAccess
from apps.core.viewsets import TenantScopedViewSet
from apps.tenants.models import School

# Models that hold a school FK but are intentionally not TenantModel subclasses.
SCHOOL_FK_ALLOWLIST = {
    "accounts.User", "tenants.SchoolSettings", "audit_logs.AuditLog",
    # Platform billing records: reached only through /platform/ endpoints (Super Admin) or, for notifications, by recipient.
    "subscriptions.Subscription", "subscriptions.SubscriptionEvent", "payments.PlatformPayment", "notifications.Notification", "notifications.EmailLog",
}


class TenantModelGuardTests(TestCase):
    def test_every_model_with_a_school_fk_is_a_tenant_model_or_allowlisted(self):
        offenders = []
        for model in apps.get_models():
            has_school_fk = any(
                getattr(field, "related_model", None) is School for field in model._meta.get_fields() if field.concrete
            )
            if has_school_fk and not issubclass(model, TenantModel) and model._meta.label not in SCHOOL_FK_ALLOWLIST:
                offenders.append(model._meta.label)
        self.assertEqual(offenders, [], "Add TenantModel as base class (or justify in SCHOOL_FK_ALLOWLIST).")

    def test_for_school_refuses_a_missing_tenant(self):
        with self.assertRaises(ValueError):
            TenantQuerySet(User).for_school(None)


class PermissionClassTests(SimpleTestCase):
    @staticmethod
    def request(**user_attrs):
        defaults = dict(is_authenticated=True, can=lambda code: True)
        return SimpleNamespace(user=SimpleNamespace(**{**defaults, **user_attrs}))

    def test_role_permission_fails_closed_when_view_declares_nothing(self):
        view = SimpleNamespace()
        self.assertFalse(HasRolePermission().has_permission(self.request(), view))

    def test_role_permission_uses_permission_map_by_action(self):
        allowed = {"list": "x.view"}
        view = SimpleNamespace(permission_map=allowed, action="list")
        self.assertTrue(HasRolePermission().has_permission(self.request(can=lambda c: c == "x.view"), view))
        view.action = "create"  # not in the map -> denied
        self.assertFalse(HasRolePermission().has_permission(self.request(), view))

    def test_role_permission_denies_anonymous(self):
        view = SimpleNamespace(required_permission="x.view")
        self.assertFalse(HasRolePermission().has_permission(self.request(is_authenticated=False), view))

    def test_platform_admin_permission(self):
        perm = IsPlatformAdmin()
        view = SimpleNamespace()
        self.assertTrue(perm.has_permission(self.request(is_active=True, is_platform_admin=True), view))
        self.assertFalse(perm.has_permission(self.request(is_active=True, is_platform_admin=False), view))
        self.assertFalse(perm.has_permission(self.request(is_active=False, is_platform_admin=True), view))

    def test_tenant_access_rejects_users_without_school(self):
        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            TenantAccess().has_permission(self.request(school_id=None), SimpleNamespace())


class TenantViewSetGuardTests(SimpleTestCase):
    def test_every_tenant_viewset_enforces_tenant_access_and_declares_permissions(self):
        self.assertTrue(TenantScopedViewSet.registry, "No tenant viewsets registered; was the app imported?")
        for viewset in TenantScopedViewSet.registry:
            self.assertIn(TenantAccess, viewset.permission_classes, viewset.__name__)
            self.assertIn(HasRolePermission, viewset.permission_classes, viewset.__name__)
            declared = getattr(viewset, "permission_map", None) or getattr(viewset, "required_permission", None)
            self.assertTrue(declared, f"{viewset.__name__} declares no permissions (it would deny everything).")
