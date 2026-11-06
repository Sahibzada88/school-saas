from rest_framework.routers import SimpleRouter

from .school_user_views import SchoolUserViewSet

router = SimpleRouter()
router.register("users", SchoolUserViewSet, basename="school-users")

urlpatterns = router.urls
