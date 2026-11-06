from rest_framework.routers import SimpleRouter

from .announcements import AnnouncementViewSet

router = SimpleRouter()
router.register("announcements", AnnouncementViewSet, basename="announcements")

urlpatterns = router.urls
