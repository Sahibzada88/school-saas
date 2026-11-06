from django.db.models import Q
from rest_framework import mixins
from rest_framework.exceptions import ValidationError

from apps.core.responses import success_response
from apps.core.viewsets import TenantScopedViewSet

from .models import User
from .roles import P
from .serializers import SchoolUserCreateSerializer, SchoolUserSerializer, SchoolUserUpdateSerializer
from .services.school_users import SchoolUserService


class SchoolUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    TenantScopedViewSet,
):
    """/api/v1/school/users/ : the school admin's own users. No DELETE: users are deactivated, never removed."""

    queryset = User.objects.select_related("school").order_by("first_name", "last_name", "email")
    serializer_class = SchoolUserSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {
        "list": P.SCHOOL_USERS,
        "retrieve": P.SCHOOL_USERS,
        "create": P.SCHOOL_USERS,
        "partial_update": P.SCHOOL_USERS,
    }

    def get_queryset(self):
        qs = super().get_queryset()  # tenant filter applied first
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search)
            )
        role = params.get("role")
        if role:
            qs = qs.filter(role=role)
        is_active = params.get("is_active")
        if is_active in {"true", "false"}:
            qs = qs.filter(is_active=(is_active == "true"))
        return qs

    def create(self, request, *args, **kwargs):
        serializer = SchoolUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = SchoolUserService.create(actor=request.user, data=serializer.validated_data, request=request)
        return success_response(SchoolUserSerializer(user).data, message="User created.", status=201)

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()  # tenant-scoped -> 404 for other schools' users
        serializer = SchoolUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            raise ValidationError({"non_field_errors": ["No changes provided."]})
        user = SchoolUserService.update(
            actor=request.user, user=user, data=serializer.validated_data, request=request
        )
        return success_response(SchoolUserSerializer(user).data, message="User updated.")
