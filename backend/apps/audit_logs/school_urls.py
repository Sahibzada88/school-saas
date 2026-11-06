from rest_framework.routers import SimpleRouter

from .views import SchoolAuditLogViewSet

router = SimpleRouter()
router.register("audit-logs", SchoolAuditLogViewSet, basename="school-audit-logs")

urlpatterns = router.urls
