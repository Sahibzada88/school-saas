from django.urls import include, path

urlpatterns = [
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/school/", include("apps.accounts.school_urls")),
    path("api/v1/school/", include("apps.tenants.urls")),
    path("api/v1/school/", include("apps.audit_logs.school_urls")),
    path("api/v1/school/", include("apps.students.urls")),
    path("api/v1/school/", include("apps.teachers.urls")),
    path("api/v1/school/", include("apps.academics.urls")),
    path("api/v1/school/", include("apps.attendance.urls")),
    path("api/v1/school/", include("apps.examinations.urls")),
    path("api/v1/school/", include("apps.fees.urls")),
    path("api/v1/school/", include("apps.reports.urls")),
    path("api/v1/school/", include("apps.notifications.school_urls")),
    path("api/v1/platform/", include("apps.platform_admin.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/plans/", include("apps.subscriptions.urls")),
    path("api/v1/", include("apps.core.urls")),
]

handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
