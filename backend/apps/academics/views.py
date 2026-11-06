from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.accounts.roles import P, Role
from apps.core.responses import success_response
from apps.core.viewsets import TenantModelViewSet, TenantScopedViewSet
from apps.students.models import Student
from apps.students.scope import visible_students
from apps.subscriptions.limits import enforce_plan_limit

from .models import AcademicSession, ClassSubject, Enrollment, EnrollmentStatus, Section, SchoolClass, Subject, TeacherAssignment, TimetableSlot
from .scope import current_session
from .serializers import (
    AcademicSessionSerializer,
    ClassSubjectSerializer,
    EnrollInputSerializer,
    EnrollmentSerializer,
    EnrollmentUpdateSerializer,
    PromoteSerializer,
    SchoolClassSerializer,
    SectionSerializer,
    SubjectSerializer,
    TeacherAssignmentSerializer,
    TimetableSlotSerializer,
)
from .services import EnrollmentService


class AcademicSessionViewSet(TenantModelViewSet):
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    ordering = ("-start_date",)

    def _unset_others(self, serializer):
        if serializer.validated_data.get("is_current"):
            AcademicSession.objects.filter(school=self.get_school(), is_current=True).exclude(
                pk=getattr(serializer.instance, "pk", None)
            ).update(is_current=False)

    def perform_create(self, serializer):
        with transaction.atomic():
            self._unset_others(serializer)
            super().perform_create(serializer)

    def perform_update(self, serializer):
        with transaction.atomic():
            self._unset_others(serializer)
            super().perform_update(serializer)


class SchoolClassViewSet(TenantModelViewSet):
    queryset = SchoolClass.objects.annotate(section_count=Count("sections", filter=Q(sections__is_deleted=False), distinct=True))
    serializer_class = SchoolClassSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    search_fields = ("name",)
    ordering = ("level_order", "name")

    def perform_create(self, serializer):
        enforce_plan_limit(self.get_school(), "classes", SchoolClass.objects.filter(school=self.get_school()).count())
        super().perform_create(serializer)


class SectionViewSet(TenantModelViewSet):
    queryset = Section.objects.select_related("school_class", "class_teacher").annotate(
        student_count=Count("enrollments", filter=Q(enrollments__session__is_current=True, enrollments__status=EnrollmentStatus.ENROLLED), distinct=True)
    )
    serializer_class = SectionSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    filter_params = {"class": "school_class_id"}
    ordering = ("school_class__level_order", "name")


class SubjectViewSet(TenantModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    search_fields = ("name", "code")
    ordering = ("name",)


class ClassSubjectViewSet(TenantModelViewSet):
    queryset = ClassSubject.objects.select_related("school_class", "subject")
    serializer_class = ClassSubjectSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    filter_params = {"class": "school_class_id"}
    ordering = ("school_class__level_order", "subject__name")


class TeacherAssignmentViewSet(TenantModelViewSet):
    queryset = TeacherAssignment.objects.select_related("teacher", "section__school_class", "subject")
    serializer_class = TeacherAssignmentSerializer
    view_permission = P.ACADEMICS_VIEW
    manage_permission = P.ACADEMICS_MANAGE
    filter_params = {"session": "session_id", "teacher": "teacher_id", "section": "section_id"}
    ordering = ("section__school_class__level_order", "section__name")

    def scope_queryset(self, queryset):
        return queryset.filter(teacher__user=self.request.user) if self.request.user.role == Role.TEACHER else queryset


class EnrollmentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, TenantScopedViewSet
):
    """Enrollments are created/changed only through the service (capacity, roll numbers, audit); never deleted."""

    queryset = Enrollment.objects.select_related("student", "session", "school_class", "section")
    serializer_class = EnrollmentSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {
        "list": P.ACADEMICS_VIEW, "retrieve": P.ACADEMICS_VIEW, "create": P.STUDENTS_MANAGE,
        "partial_update": P.STUDENTS_MANAGE, "promote": P.STUDENTS_LIFECYCLE,
    }
    filter_params = {"session": "session_id", "section": "section_id", "class": "school_class_id", "student": "student_id", "status": "status"}

    def scope_queryset(self, queryset):
        students = visible_students(self.request.user, Student.objects.filter(school=self.request.user.school))
        return queryset.filter(student__in=students)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            params = self.request.query_params
            try:
                for param, lookup in self.filter_params.items():
                    if params.get(param):
                        queryset = queryset.filter(**{lookup: params[param].strip()})
            except (ValueError, DjangoValidationError) as exc:  # invalid UUID in a filter -> 400, never 500
                raise ValidationError({"detail": ["Invalid filter value."]}) from exc
            queryset = queryset.order_by("section__school_class__level_order", "section__name", "roll_number")
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = EnrollInputSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        session = data.get("session") or current_session(self.get_school())
        if session is None:
            raise ValidationError({"session": ["There is no current academic session. Create one first."]})
        enrollment = EnrollmentService.enroll(
            school=self.get_school(), student=data["student"], session=session, section=data["section"],
            roll_number=data.get("roll_number"), actor=request.user, request=request,
        )
        return success_response(EnrollmentSerializer(self.get_queryset().get(pk=enrollment.pk)).data, message="Student enrolled.", status=201)

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        serializer = EnrollmentUpdateSerializer(data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        EnrollmentService.move(
            enrollment=enrollment, section=serializer.validated_data.get("section"),
            roll_number=serializer.validated_data.get("roll_number"), actor=request.user, request=request,
        )
        return success_response(EnrollmentSerializer(self.get_queryset().get(pk=enrollment.pk)).data, message="Enrollment updated.")

    @action(detail=False, methods=["post"])
    def promote(self, request):
        serializer = PromoteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        counts = EnrollmentService.promote(
            school=self.get_school(), from_session=data["from_session"], to_session=data["to_session"],
            promote_to=data.get("promote_to"), repeat_to=data.get("repeat_to"), decisions=data["decisions"],
            actor=request.user, request=request,
        )
        return success_response(counts, message="Year-end processing completed.")


class TimetableSlotViewSet(TenantModelViewSet):
    queryset = TimetableSlot.objects.select_related("section__school_class", "subject", "teacher")
    serializer_class = TimetableSlotSerializer
    view_permission = P.TIMETABLE_VIEW
    manage_permission = P.TIMETABLE_MANAGE
    filter_params = {"session": "session_id", "section": "section_id", "teacher": "teacher_id"}
    ordering = ("weekday", "period_no")

    def scope_queryset(self, queryset):
        user = self.request.user
        if user.role == Role.TEACHER:
            return queryset.filter(teacher__user=user)
        if user.role in (Role.PARENT, Role.STUDENT):
            students = visible_students(user, Student.objects.filter(school=user.school))
            sections = Enrollment.objects.filter(student__in=students, session__is_current=True).values("section_id")
            return queryset.filter(section_id__in=sections)
        return queryset
