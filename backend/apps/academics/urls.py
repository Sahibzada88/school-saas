from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("sessions", views.AcademicSessionViewSet, basename="sessions")
router.register("classes", views.SchoolClassViewSet, basename="classes")
router.register("sections", views.SectionViewSet, basename="sections")
router.register("subjects", views.SubjectViewSet, basename="subjects")
router.register("class-subjects", views.ClassSubjectViewSet, basename="class-subjects")
router.register("teacher-assignments", views.TeacherAssignmentViewSet, basename="teacher-assignments")
router.register("enrollments", views.EnrollmentViewSet, basename="enrollments")
router.register("timetable", views.TimetableSlotViewSet, basename="timetable")

urlpatterns = router.urls
