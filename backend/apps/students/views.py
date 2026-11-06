from django.db.models import Prefetch
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser

from apps.accounts.roles import P
from apps.core.responses import success_response
from apps.core.viewsets import TenantModelViewSet

from apps.reports.csv_service import CSVExportService

from .importer import TEMPLATE_HEADER, TEMPLATE_ROWS, StudentImportService
from .models import Guardian, Student, StudentDocument, StudentGuardian
from .scope import visible_guardians, visible_students
from .serializers import (
    GuardianSerializer,
    LinkGuardianSerializer,
    StatusChangeSerializer,
    StudentDetailSerializer,
    StudentDocumentSerializer,
    StudentGuardianSerializer,
    StudentListSerializer,
    StudentWriteSerializer,
)
from .services import StudentService

UUID_PART = "[0-9a-fA-F-]{36}"


class StudentViewSet(TenantModelViewSet):
    """/api/v1/school/students/ : admission, profile, status changes. Role-scoped (teacher: own sections, parent: own
    children, student: self)."""

    queryset = Student.objects.all()
    view_permission = P.STUDENTS_VIEW
    manage_permission = P.STUDENTS_MANAGE
    delete_permission = P.STUDENTS_LIFECYCLE
    permission_map = {
        "list": P.STUDENTS_VIEW, "retrieve": P.STUDENTS_VIEW, "create": P.STUDENTS_MANAGE, "partial_update": P.STUDENTS_MANAGE,
        "destroy": P.STUDENTS_LIFECYCLE, "change_status": P.STUDENTS_LIFECYCLE,
        "guardians": P.STUDENTS_VIEW, "link_guardian": P.GUARDIANS_MANAGE, "unlink_guardian": P.GUARDIANS_MANAGE,
        "import_students": P.STUDENTS_MANAGE, "import_template": P.STUDENTS_MANAGE,
    }
    filter_params = {"status": "status", "gender": "gender", "section": "enrollments__section_id", "class": "enrollments__school_class_id"}
    search_fields = ("first_name", "last_name", "student_number", "phone")
    ordering_fields = ("first_name", "last_name", "student_number", "admission_date", "created_at")
    ordering = ("first_name", "last_name")

    def scope_queryset(self, queryset):
        return visible_students(self.request.user, queryset)

    def get_queryset(self):
        from apps.academics.models import Enrollment

        queryset = super().get_queryset().distinct() if self.action == "list" else super().get_queryset()
        current = Enrollment.objects.filter(session__is_current=True).select_related("school_class", "section")
        queryset = queryset.prefetch_related(Prefetch("enrollments", queryset=current, to_attr="current_enrollments"))
        if self.action in ("retrieve", "partial_update"):
            queryset = queryset.prefetch_related("guardian_links__guardian")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return StudentListSerializer
        if self.action in ("create", "partial_update"):
            return StudentWriteSerializer
        return StudentDetailSerializer

    def _detail(self, student):
        return StudentDetailSerializer(self.get_queryset().get(pk=student.pk), context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = StudentWriteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        student = StudentService.admit(school=self.get_school(), data=serializer.validated_data, actor=request.user, request=request)
        return success_response(self._detail(student), message="Student admitted.", status=201)

    def partial_update(self, request, *args, **kwargs):
        student = self.get_object()
        serializer = StudentWriteSerializer(student, data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        StudentService.update(student=student, data=serializer.validated_data, actor=request.user, request=request)
        return success_response(self._detail(student), message="Student updated.")

    def perform_destroy(self, instance):
        StudentService.delete(student=instance, actor=self.request.user, request=self.request)

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser, FormParser])
    def import_students(self, request):
        """CSV import. `dry_run=true` only validates and reports row errors; nothing is written unless every row is valid."""
        dry_run = str(request.data.get("dry_run", "true")).lower() != "false"
        report = StudentImportService.run(school=self.get_school(), uploaded=request.FILES.get("file"), dry_run=dry_run, actor=request.user, request=request)
        message = "File checked." if dry_run else f"{report['created']} student(s) imported."
        return success_response(report, message=message)

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        return CSVExportService.respond("students-import-template", TEMPLATE_HEADER, TEMPLATE_ROWS)

    @action(detail=True, methods=["post"], url_path="change-status")
    def change_status(self, request, pk=None):
        student = self.get_object()
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        StudentService.change_status(
            student=student, status=serializer.validated_data["status"], reason=serializer.validated_data["reason"],
            actor=request.user, request=request,
        )
        return success_response(self._detail(student), message="Status updated.")

    @action(detail=True, methods=["get"], url_path="guardians")
    def guardians(self, request, pk=None):
        student = self.get_object()
        links = student.guardian_links.select_related("guardian")
        return success_response(StudentGuardianSerializer(links, many=True).data, message="")

    @guardians.mapping.post
    def link_guardian(self, request, pk=None):
        student = self.get_object()
        serializer = LinkGuardianSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        link = StudentService.link_guardian(student=student, data=serializer.validated_data, actor=request.user, request=request)
        link = StudentGuardian.objects.select_related("guardian").get(pk=link.pk)
        return success_response(StudentGuardianSerializer(link).data, message="Guardian linked.", status=201)

    @action(detail=True, methods=["delete"], url_path=rf"guardians/(?P<link_id>{UUID_PART})")
    def unlink_guardian(self, request, pk=None, link_id=None):
        student = self.get_object()
        link = StudentGuardian.objects.select_related("guardian", "student").filter(student=student, pk=link_id).first()
        if link is None:
            raise NotFound()
        StudentService.unlink_guardian(link=link, actor=request.user, request=request)
        return success_response(None, message="Guardian unlinked.")


class GuardianViewSet(TenantModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = GuardianSerializer
    view_permission = P.STUDENTS_VIEW
    manage_permission = P.GUARDIANS_MANAGE
    filter_params = {"student": "student_links__student_id"}
    search_fields = ("first_name", "last_name", "phone", "national_id")
    ordering = ("first_name", "last_name")

    def scope_queryset(self, queryset):
        return visible_guardians(self.request.user, queryset)


class StudentDocumentViewSet(TenantModelViewSet):
    queryset = StudentDocument.objects.select_related("student")
    serializer_class = StudentDocumentSerializer
    view_permission = P.STUDENTS_VIEW
    manage_permission = P.STUDENTS_MANAGE
    filter_params = {"student": "student_id"}
    ordering = ("-created_at",)

    def scope_queryset(self, queryset):
        students = visible_students(self.request.user, Student.objects.filter(school=self.request.user.school))
        return queryset.filter(student__in=students)
