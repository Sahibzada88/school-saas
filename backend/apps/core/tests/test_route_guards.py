"""Structural guards: every routed school/platform view must use the protected base classes and declare
valid permission codes, so a forgotten permission or tenant filter fails CI instead of shipping."""
import config.urls  # noqa: F401
from django.test import SimpleTestCase

from apps.accounts.roles import ALL_PERMISSIONS, PLATFORM_PERMISSIONS
from apps.core.permissions import HasRolePermission, IsPlatformAdmin, TenantAccess
from apps.core.testing import iter_routed_views
from apps.core.viewsets import (
    PlatformAPIView,
    PlatformViewSet,
    TenantAPIView,
    TenantScopedViewSet,
    platform_view_registry,
)

SCHOOL_PREFIX = "api/v1/school/"
PLATFORM_PREFIX = "api/v1/platform/"


def declared_codes(view_class) -> set[str]:
    mapping = getattr(view_class, "permission_map", None) or {}
    codes = set(mapping.values())
    single = getattr(view_class, "required_permission", None)
    if single:
        codes.add(single)
    return codes


class RouteGuardTests(SimpleTestCase):
    def test_school_routes_use_tenant_base_classes(self):
        routes = list(iter_routed_views(SCHOOL_PREFIX))
        self.assertTrue(routes)
        for route, view_class in routes:
            self.assertTrue(issubclass(view_class, (TenantScopedViewSet, TenantAPIView)), route)
            self.assertIn(TenantAccess, view_class.permission_classes, route)
            self.assertIn(HasRolePermission, view_class.permission_classes, route)

    def test_platform_routes_use_platform_base_classes(self):
        routes = list(iter_routed_views(PLATFORM_PREFIX))
        self.assertTrue(routes)
        for route, view_class in routes:
            self.assertTrue(issubclass(view_class, (PlatformViewSet, PlatformAPIView)), route)
            self.assertIn(IsPlatformAdmin, view_class.permission_classes, route)
            self.assertIn(HasRolePermission, view_class.permission_classes, route)

    def test_every_routed_view_declares_known_permission_codes(self):
        for prefix in (SCHOOL_PREFIX, PLATFORM_PREFIX):
            for route, view_class in iter_routed_views(prefix):
                codes = declared_codes(view_class)
                self.assertTrue(codes, f"{route} declares no permission (it would deny everyone)")
                self.assertLessEqual(codes, ALL_PERMISSIONS, f"{route} uses an unknown permission code")

    def test_platform_views_only_use_platform_permissions(self):
        self.assertTrue(platform_view_registry)
        for view_class in platform_view_registry:
            codes = declared_codes(view_class)
            self.assertTrue(codes, view_class.__name__)
            self.assertLessEqual(codes, PLATFORM_PERMISSIONS, view_class.__name__)

    def test_billing_routes_are_registered_under_the_platform_prefix(self):
        routes = " ".join(route for route, _ in iter_routed_views(PLATFORM_PREFIX))
        for fragment in ("plans", "subscriptions", "payments", "settings", "schools"):
            self.assertIn(fragment, routes)

    def test_school_views_never_use_platform_permissions(self):
        for route, view_class in iter_routed_views(SCHOOL_PREFIX):
            self.assertFalse(declared_codes(view_class) & PLATFORM_PERMISSIONS, route)
