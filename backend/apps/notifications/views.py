from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from apps.accounts.roles import P
from apps.core.permissions import HasRolePermission
from apps.core.responses import success_response
from apps.subscriptions.services import SubscriptionService

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """/api/v1/notifications/ : the caller's OWN notifications. Scoped by recipient (not by school), so a suspended
    school's admin can still read why. Other users' notifications are 404."""

    permission_classes = [IsAuthenticated, HasRolePermission]
    serializer_class = NotificationSerializer
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {
        "list": P.NOTIFICATIONS_VIEW,
        "unread_count": P.NOTIFICATIONS_VIEW,
        "read": P.NOTIFICATIONS_VIEW,
        "mark_all_read": P.NOTIFICATIONS_VIEW,
    }

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).order_by("-created_at")
        if self.request.query_params.get("unread") == "true":
            qs = qs.filter(is_read=False)
        return qs

    def _lazy_generate(self):
        """Request-time generation of billing notices (no background worker exists)."""
        school = getattr(self.request.user, "school", None)
        if school is not None:
            SubscriptionService.sync_quietly(school)

    def list(self, request, *args, **kwargs):
        self._lazy_generate()
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        self._lazy_generate()
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return success_response({"count": count}, message="")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        NotificationService.mark_read(Notification.objects.filter(pk=notification.pk))
        notification.refresh_from_db()
        return success_response(NotificationSerializer(notification).data, message="")

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = NotificationService.mark_read(Notification.objects.filter(recipient=request.user))
        return success_response({"updated": updated}, message="")
