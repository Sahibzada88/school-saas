from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from .exceptions import Conflict

from .permissions import HasRolePermission, IsPlatformAdmin, TenantAccess

# Every platform (Super Admin) view registers here; guard tests iterate it.
platform_view_registry: list[type] = []


def _school_of(request):
    school = getattr(request.user, "school", None)
    if school is None:
        raise PermissionDenied("This resource belongs to a school account.", code="tenant_required")
    return school


class TenantScopedViewSet(viewsets.GenericViewSet):
    """Base for every school-owned collection resource.

    * The tenant is ALWAYS request.user.school, never request data or query params.
    * get_queryset() is filtered by the tenant, so detail routes of another school's objects are 404.
    * Permissions fail closed: declare `permission_map` (per action) or `required_permission`.
    Subclasses register themselves in `registry`, which the isolation test harness iterates.
    """

    permission_classes = [TenantAccess, HasRolePermission]
    tenant_field = "school"
    registry: list[type] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("abstract", False):
            TenantScopedViewSet.registry.append(cls)

    def get_school(self):
        return _school_of(self.request)

    def scope_queryset(self, queryset):
        """Role-based narrowing (teacher: own sections, parent: own children...). Runs after the tenant filter."""
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset().filter(**{self.tenant_field: self.get_school()})
        return self.scope_queryset(queryset)


class TenantModelViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    TenantScopedViewSet,
):
    """Tenant CRUD with fail-closed permissions derived from `view_permission` / `manage_permission` (/ `delete_permission`).

    Subclass attributes: queryset, serializer_class, view_permission, manage_permission, filter_params
    ({"query_param": "orm_lookup"}), search_fields, ordering_fields, ordering. Disable verbs with `http_method_names`."""

    abstract = True
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    view_permission: str | None = None
    manage_permission: str | None = None
    delete_permission: str | None = None
    filter_params: dict = {}
    search_fields: tuple = ()
    ordering_fields: tuple = ()
    ordering: tuple = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.view_permission and "permission_map" not in cls.__dict__:
            manage = cls.manage_permission
            mapping = {"list": cls.view_permission, "retrieve": cls.view_permission}
            if manage:
                mapping.update(create=manage, partial_update=manage, update=manage, destroy=cls.delete_permission or manage)
            cls.permission_map = mapping

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
        params = self.request.query_params
        try:
            for param, lookup in self.filter_params.items():
                value = params.get(param, "").strip()
                if value:
                    queryset = queryset.filter(**{lookup: value})
            search = params.get("search", "").strip()
            if search and self.search_fields:
                condition = Q()
                for field in self.search_fields:
                    condition |= Q(**{f"{field}__icontains": search})
                queryset = queryset.filter(condition)
            ordering = params.get("ordering", "")
            if ordering and ordering.lstrip("-") in self.ordering_fields:
                queryset = queryset.order_by(ordering)
            elif self.ordering:
                queryset = queryset.order_by(*self.ordering)
            return queryset
        except (DjangoValidationError, ValueError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(school=self.get_school())
        except IntegrityError as exc:
            raise Conflict("A record with these details already exists or conflicts with another.", code="duplicate") from exc

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            raise Conflict("These details conflict with an existing record.", code="duplicate") from exc

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise Conflict("This item is in use and cannot be deleted.", code="in_use") from exc


class TenantAPIView(APIView):
    """Base for school-level singleton endpoints (profile, dashboard). The school is always the caller's own."""

    permission_classes = [TenantAccess, HasRolePermission]

    def get_school(self):
        return _school_of(self.request)


class PlatformViewSet(viewsets.GenericViewSet):
    """Base for Super Admin collection resources. IsPlatformAdmin is enforced on the base class itself."""

    permission_classes = [IsPlatformAdmin, HasRolePermission]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        platform_view_registry.append(cls)


class PlatformAPIView(APIView):
    permission_classes = [IsPlatformAdmin, HasRolePermission]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        platform_view_registry.append(cls)
