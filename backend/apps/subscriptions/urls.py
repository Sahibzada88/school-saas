from django.urls import path

from .views import PublicPlanListView

app_name = "subscriptions"

urlpatterns = [path("", PublicPlanListView.as_view(), name="public-plans")]
