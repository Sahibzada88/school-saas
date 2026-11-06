from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("exam-types", views.ExamTypeViewSet, basename="exam-types")
router.register("grading-scales", views.GradingScaleViewSet, basename="grading-scales")
router.register("exams", views.ExamViewSet, basename="exams")
router.register("exam-subjects", views.ExamSubjectViewSet, basename="exam-subjects")
router.register("results", views.ResultViewSet, basename="results")

urlpatterns = [path("results/transcript/<uuid:student_id>/", views.TranscriptView.as_view(), name="transcript")] + router.urls
