from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("attendance/records", views.AttendanceRecordViewSet, basename="attendance-records")
router.register("attendance/teacher-records", views.TeacherAttendanceRecordViewSet, basename="teacher-attendance-records")

urlpatterns = [
    path("attendance/roster/", views.AttendanceRosterView.as_view(), name="attendance-roster"),
    path("attendance/mark/", views.AttendanceMarkView.as_view(), name="attendance-mark"),
    path("attendance/monthly/", views.AttendanceMonthlyView.as_view(), name="attendance-monthly"),
    path("attendance/teachers/", views.TeacherAttendanceView.as_view(), name="teacher-attendance"),
] + router.urls
