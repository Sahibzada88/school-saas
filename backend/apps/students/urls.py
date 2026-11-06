from rest_framework.routers import SimpleRouter

from .views import GuardianViewSet, StudentDocumentViewSet, StudentViewSet

router = SimpleRouter()
router.register("students", StudentViewSet, basename="students")
router.register("guardians", GuardianViewSet, basename="guardians")
router.register("student-documents", StudentDocumentViewSet, basename="student-documents")

urlpatterns = router.urls
