from rest_framework import mixins

from apps.accounts.roles import P
from apps.core.viewsets import TenantScopedViewSet

from .models import AuditLog
from .serializers import SchoolAuditLogSerializer


class SchoolAuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    """/api/v1/school/audit-logs/ : the school's own activity trail, read-only."""

    queryset = AuditLog.objects.select_related("actor").order_by("-created_at")
    serializer_class = SchoolAuditLogSerializer
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {"list": P.SCHOOL_AUDIT, "retrieve": P.SCHOOL_AUDIT}

    def get_queryset(self):
        qs = super().get_queryset()  # tenant filter first
        params = self.request.query_params
        action = params.get("action", "").strip()
        if action:
            qs = qs.filter(action=action)
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(description__icontains=search)
        return qs
