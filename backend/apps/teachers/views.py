from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from apps.accounts.roles import P, Role
from apps.core.responses import success_response
from apps.core.viewsets import TenantModelViewSet

from apps.reports.csv_service import CSVExportService

from .importer import TEMPLATE_HEADER, TEMPLATE_ROWS, TeacherImportService
from .models import Teacher
from .serializers import TeacherDetailSerializer, TeacherListSerializer, TeacherWriteSerializer
from .services import TeacherService


class TeacherViewSet(TenantModelViewSet):
    """/api/v1/school/teachers/. Teachers see only themselves; admin and receptionist see everyone."""

    queryset = Teacher.objects.all()
    view_permission = P.TEACHERS_VIEW
    manage_permission = P.TEACHERS_MANAGE
    permission_map = {
        "list": P.TEACHERS_VIEW, "retrieve": P.TEACHERS_VIEW, "create": P.TEACHERS_MANAGE, "partial_update": P.TEACHERS_MANAGE,
        "destroy": P.TEACHERS_MANAGE, "import_teachers": P.TEACHERS_MANAGE, "import_template": P.TEACHERS_MANAGE,
    }
    filter_params = {"status": "status"}
    search_fields = ("first_name", "last_name", "employee_id", "phone", "email")
    ordering_fields = ("first_name", "last_name", "employee_id", "joining_date")
    ordering = ("first_name", "last_name")

    def scope_queryset(self, queryset):
        return queryset.filter(user=self.request.user) if self.request.user.role == Role.TEACHER else queryset

    def get_serializer_class(self):
        if self.action == "list":
            return TeacherListSerializer
        if self.action in ("create", "partial_update"):
            return TeacherWriteSerializer
        return TeacherDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = TeacherWriteSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        teacher = TeacherService.create(school=self.get_school(), data=serializer.validated_data, actor=request.user, request=request)
        return success_response(TeacherDetailSerializer(teacher, context=self.get_serializer_context()).data, message="Teacher added.", status=201)

    def partial_update(self, request, *args, **kwargs):
        teacher = self.get_object()
        serializer = TeacherWriteSerializer(teacher, data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        TeacherService.update(teacher=teacher, data=serializer.validated_data, actor=request.user, request=request)
        return success_response(TeacherDetailSerializer(teacher, context=self.get_serializer_context()).data, message="Teacher updated.")

    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser, FormParser])
    def import_teachers(self, request):
        dry_run = str(request.data.get("dry_run", "true")).lower() != "false"
        report = TeacherImportService.run(school=self.get_school(), uploaded=request.FILES.get("file"), dry_run=dry_run, actor=request.user, request=request)
        return success_response(report, message="File checked." if dry_run else f"{report['created']} teacher(s) imported.")

    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        return CSVExportService.respond("teachers-import-template", TEMPLATE_HEADER, TEMPLATE_ROWS)

    def perform_destroy(self, instance):
        TeacherService.delete(teacher=instance, actor=self.request.user, request=self.request)
