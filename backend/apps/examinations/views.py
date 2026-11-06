from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.roles import P, Role
from apps.core.exceptions import Conflict
from apps.core.responses import success_response
from apps.core.viewsets import TenantAPIView, TenantModelViewSet, TenantScopedViewSet
from apps.students.models import Student
from apps.students.scope import visible_students

from .models import Exam, ExamStatus, ExamSubject, ExamType, GradingScale, ReportCard
from .serializers import (
    ExamSerializer,
    ExamSubjectSerializer,
    ExamTypeSerializer,
    GradingScaleSerializer,
    PublishSerializer,
    ReportCardDetailSerializer,
    RemarksSerializer,
    ReportCardListSerializer,
    SaveMarksSerializer,
)
from .services import ExamService, GradingService, MarksService, ResultService


class ExamTypeViewSet(TenantModelViewSet):
    queryset = ExamType.objects.all()
    serializer_class = ExamTypeSerializer
    view_permission = P.RESULTS_VIEW
    manage_permission = P.EXAMS_MANAGE
    ordering = ("name",)


class GradingScaleViewSet(TenantModelViewSet):
    queryset = GradingScale.objects.prefetch_related("bands")
    serializer_class = GradingScaleSerializer
    view_permission = P.RESULTS_VIEW
    manage_permission = P.EXAMS_MANAGE
    ordering = ("name",)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        scale = GradingScale(school=self.get_school(), name=data["name"])
        GradingService.save_scale(scale=scale, is_default=data.get("is_default"), bands=data.get("bands"))
        return success_response(GradingScaleSerializer(self.get_queryset().get(pk=scale.pk)).data, message="Grading scale saved.", status=201)

    def partial_update(self, request, *args, **kwargs):
        scale = self.get_object()
        serializer = self.get_serializer(scale, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        GradingService.save_scale(scale=scale, name=data.get("name"), is_default=data.get("is_default"), bands=data.get("bands"))
        return success_response(GradingScaleSerializer(self.get_queryset().get(pk=scale.pk)).data, message="Grading scale saved.")


class ExamViewSet(TenantModelViewSet):
    queryset = Exam.objects.select_related("session", "exam_type").annotate(subject_count=Count("subjects", distinct=True))
    serializer_class = ExamSerializer
    view_permission = P.RESULTS_VIEW
    manage_permission = P.EXAMS_MANAGE
    permission_map = {
        "list": P.RESULTS_VIEW, "retrieve": P.RESULTS_VIEW, "create": P.EXAMS_MANAGE, "partial_update": P.EXAMS_MANAGE,
        "destroy": P.EXAMS_MANAGE, "schedule": P.EXAMS_MANAGE, "open_marks": P.EXAMS_MANAGE, "archive": P.EXAMS_MANAGE,
        "publish": P.RESULTS_PUBLISH, "preview": P.RESULTS_PUBLISH, "marks": P.MARKS_ENTER, "save_marks": P.MARKS_ENTER,
        "subjects": P.RESULTS_VIEW,
    }
    filter_params = {"session": "session_id", "status": "status", "type": "exam_type_id"}
    search_fields = ("name",)
    ordering_fields = ("start_date", "name", "created_at")
    ordering = ("-start_date", "name")

    def scope_queryset(self, queryset):
        role = self.request.user.role
        if role == Role.SCHOOL_ADMIN:
            return queryset
        if role == Role.TEACHER:
            return queryset.exclude(status=ExamStatus.DRAFT)
        return queryset.filter(status__in=[ExamStatus.PUBLISHED, ExamStatus.ARCHIVED])

    def perform_create(self, serializer):
        school = self.get_school()
        scale = serializer.validated_data.get("grading_scale") or GradingScale.objects.filter(school=school).order_by("-is_default", "name").first()
        if scale is None:
            raise ValidationError({"grading_scale": ["Create a grading scale first."]})
        try:
            with transaction.atomic():
                serializer.save(school=school, grading_scale=scale)
        except IntegrityError as exc:
            raise Conflict("An exam with these details already exists.", code="duplicate") from exc

    def perform_destroy(self, instance):
        if instance.status != ExamStatus.DRAFT:
            raise Conflict("Only draft exams can be deleted. Archive finished exams instead.", code="invalid_transition")
        super().perform_destroy(instance)

    def _fresh(self, exam):
        return success_response(ExamSerializer(self.get_queryset().get(pk=exam.pk)).data, message="")

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        return self._fresh(ExamService.transition(exam=self.get_object(), action="schedule"))

    @action(detail=True, methods=["post"], url_path="open-marks")
    def open_marks(self, request, pk=None):
        return self._fresh(ExamService.transition(exam=self.get_object(), action="open_marks"))

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return self._fresh(ExamService.transition(exam=self.get_object(), action="archive"))

    @action(detail=True, methods=["get"])
    def subjects(self, request, pk=None):
        exam = self.get_object()
        rows = ExamSubject.objects.filter(exam=exam).select_related("school_class", "subject").order_by("school_class__level_order", "subject__name")
        return success_response(ExamSubjectSerializer(rows, many=True, context=self.get_serializer_context()).data, message="")

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """Results computed on the fly from live marks (nothing stored). Shows missing marks before publishing."""
        exam = self.get_object()
        results = [ResultService.serialize_preview(r) for r in ResultService.compute(exam)]
        return success_response({"exam": exam.name, "status": exam.status, "results": results}, message="")

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam = self.get_object()
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summary = ExamService.publish(exam=exam, force=serializer.validated_data["force"], actor=request.user, request=request)
        return success_response(summary, message="Results published.")

    @action(detail=True, methods=["get"])
    def marks(self, request, pk=None):
        exam = self.get_object()
        subject_id = request.query_params.get("exam_subject")
        try:
            exam_subject = ExamSubject.objects.select_related("exam", "subject", "school_class").filter(exam=exam, pk=subject_id).first()
        except (ValueError, DjangoValidationError):
            exam_subject = None
        if exam_subject is None:
            raise NotFound()
        return success_response(
            {"total_marks": exam_subject.total_marks, "passing_marks": exam_subject.passing_marks, "open": exam.status in (ExamStatus.SCHEDULED, ExamStatus.MARKS_ENTRY),
             "rows": MarksService.roster(user=request.user, exam_subject=exam_subject)}, message="",
        )

    @marks.mapping.post
    def save_marks(self, request, pk=None):
        exam = self.get_object()
        serializer = SaveMarksSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        exam_subject = serializer.validated_data["exam_subject"]
        if exam_subject.exam_id != exam.id:
            raise ValidationError({"exam_subject": ["This subject does not belong to the exam."]})
        saved = MarksService.save(user=request.user, exam=exam, exam_subject=exam_subject, entries=[dict(e) for e in serializer.validated_data["entries"]])
        return success_response({"saved": saved}, message="Marks saved.")


class ExamSubjectViewSet(TenantModelViewSet):
    queryset = ExamSubject.objects.select_related("exam", "school_class", "subject")
    serializer_class = ExamSubjectSerializer
    view_permission = P.RESULTS_VIEW
    manage_permission = P.EXAMS_MANAGE
    filter_params = {"exam": "exam_id", "class": "school_class_id"}
    ordering = ("school_class__level_order", "subject__name")

    def scope_queryset(self, queryset):
        role = self.request.user.role
        if role == Role.SCHOOL_ADMIN:
            return queryset
        if role == Role.TEACHER:
            return queryset.exclude(exam__status=ExamStatus.DRAFT)
        return queryset.filter(exam__status__in=[ExamStatus.PUBLISHED, ExamStatus.ARCHIVED])

    @staticmethod
    def _require_editable(exam):
        if exam.status not in (ExamStatus.DRAFT, ExamStatus.SCHEDULED):
            raise Conflict("The schedule can no longer be changed once marks entry has started.", code="exam_locked")

    def perform_create(self, serializer):
        self._require_editable(serializer.validated_data["exam"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._require_editable(serializer.instance.exam)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._require_editable(instance.exam)
        super().perform_destroy(instance)


def scoped_report_cards(user):
    """Published report cards this user may read: admin all, teacher own sections, parent children, student self."""
    queryset = ReportCard.objects.filter(school=user.school, is_published=True).select_related(
        "exam__session", "student", "enrollment__school_class", "enrollment__section", "school"
    )
    if user.role == Role.SCHOOL_ADMIN:
        return queryset
    students = visible_students(user, Student.objects.filter(school=user.school))
    return queryset.filter(student__in=students)


class ResultViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    """/api/v1/school/results/ : published report cards as JSON (rendered by the frontend; PDFs are generated on request)."""

    queryset = ReportCard.objects.all()
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {"list": P.RESULTS_VIEW, "retrieve": P.RESULTS_VIEW, "remarks": P.MARKS_ENTER}

    def get_queryset(self):
        queryset = scoped_report_cards(self.request.user)
        params = self.request.query_params
        try:
            for param, lookup in {"exam": "exam_id", "student": "student_id", "section": "enrollment__section_id", "class": "enrollment__school_class_id"}.items():
                if params.get(param):
                    queryset = queryset.filter(**{lookup: params[param]})
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc
        return queryset.order_by("exam__start_date", "enrollment__section__name", "position_section", "student__first_name")

    def get_serializer_class(self):
        return ReportCardListSerializer if self.action == "list" else ReportCardDetailSerializer

    @action(detail=True, methods=["post"])
    def remarks(self, request, pk=None):
        """Teacher remarks (teachers: only their own sections' students; admin: any) and principal remarks (admin only)."""
        card = self.get_object()
        serializer = RemarksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if "principal_remarks" in data and request.user.role != Role.SCHOOL_ADMIN:
            raise PermissionDenied("Only the School Admin can write the principal's remarks.")
        for field_name, value in data.items():
            setattr(card, field_name, value)
        card.save(update_fields=[*data.keys(), "updated_at"])
        return success_response(ReportCardDetailSerializer(card).data, message="Remarks saved.")


class TranscriptView(TenantAPIView):
    """All published results of one student, grouped by exam."""

    required_permission = P.RESULTS_VIEW

    def get(self, request, student_id):
        cards = list(scoped_report_cards(request.user).filter(student_id=student_id).order_by("exam__session__start_date", "exam__start_date"))
        if not cards:
            raise NotFound()
        student = cards[0].student
        return success_response({
            "student": {"id": str(student.id), "name": student.full_name, "student_number": student.student_number},
            "school": cards[0].school.name,
            "exams": [ReportCardDetailSerializer(card).data for card in cards],
        }, message="")
