from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("profile/", views.SchoolProfileView.as_view(), name="school-profile"),
    path("images/<uuid:image_id>/", views.SchoolImageView.as_view(), name="school-image"),
    path("dashboard/", views.SchoolDashboardView.as_view(), name="school-dashboard"),
]
