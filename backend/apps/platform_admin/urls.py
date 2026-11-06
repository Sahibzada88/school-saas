from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "platform_admin"

router = SimpleRouter()
router.register("schools", views.PlatformSchoolViewSet, basename="platform-schools")
router.register("plans", views.PlatformPlanViewSet, basename="platform-plans")
router.register("subscriptions", views.PlatformSubscriptionViewSet, basename="platform-subscriptions")
router.register("payments", views.PlatformPaymentViewSet, basename="platform-payments")
router.register("audit-logs", views.PlatformAuditLogViewSet, basename="platform-audit-logs")

urlpatterns = [
    path("dashboard/", views.PlatformDashboardView.as_view(), name="platform-dashboard"),
    path("settings/", views.PlatformSettingsView.as_view(), name="platform-settings"),
] + router.urls
