from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.dateparse import parse_date
from rest_framework import mixins
from rest_framework.exceptions import NotFound, ValidationError

from apps.academics.models import Section
from apps.academics.scope import assigned_section_ids
from apps.accounts.roles import P, Role
from apps.core.responses import success_response
from apps.core.viewsets import TenantAPIView, TenantScopedViewSet
from apps.students.models import Student
from apps.students.scope import visible_students

from .models import StudentAttendance, TeacherAttendance
from .serializers import (
    MarkStudentsSerializer,
    MarkTeachersSerializer,
    StudentAttendanceSerializer,
    TeacherAttendanceSerializer,
)
from .services import StudentAttendanceService, TeacherAttendanceService


def _date_param(request, name: str, default: date | None = None) -> date:
    raw = request.query_params.get(name, "")
    if not raw:
        if default is None:
            raise ValidationError({name: ["This query parameter is required (YYYY-MM-DD)."]})
        return default
    try:
        parsed = parse_date(raw)
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValidationError({name: ["Use YYYY-MM-DD."]})
    return parsed


def _section_or_404(school, section_id) -> Section:
    try:
        section = Section.objects.select_related("school_class").filter(school=school, pk=section_id).first()
    except (ValueError, DjangoValidationError):  # malformed id
        section = None
    if section is None:
        raise NotFound()
    return section


def scoped_attendance(user):
    """StudentAttendance rows this user may read."""
    queryset = StudentAttendance.objects.filter(school=user.school).select_related("student", "section__school_class")
    if user.role == Role.TEACHER:
        return queryset.filter(section_id__in=assigned_section_ids(user))
    if user.role in (Role.PARENT, Role.STUDENT):
        return queryset.filter(student__in=visible_students(user, Student.objects.filter(school=user.school)))
    return queryset


class AttendanceRosterView(TenantAPIView):
    """GET roster for a section and date (existing marks included)."""

    required_permission = P.ATTENDANCE_STUDENTS_MARK

    def get(self, request):
        day = _date_param(request, "date", default=date.today())
        section = _section_or_404(self.get_school(), request.query_params.get("section"))
        return success_response(StudentAttendanceService.roster(user=request.user, section=section, day=day), message="")


class AttendanceMarkView(TenantAPIView):
    required_permission = P.ATTENDANCE_STUDENTS_MARK

    def post(self, request):
        serializer = MarkStudentsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        saved = StudentAttendanceService.mark(
            school=self.get_school(), user=request.user, section=data["section"], day=data["date"],
            records=[dict(r) for r in data["records"]],
        )
        return success_response({"saved": saved}, message="Attendance saved.")


class AttendanceRecordViewSet(mixins.ListModelMixin, TenantScopedViewSet):
    """History: /school/attendance/records/?student=&section=&date_from=&date_to="""

    queryset = StudentAttendance.objects.select_related("student", "section__school_class")
    serializer_class = StudentAttendanceSerializer
    permission_map = {"list": P.ATTENDANCE_STUDENTS_VIEW}

    def scope_queryset(self, queryset):
        user = self.request.user
        if user.role == Role.TEACHER:
            return queryset.filter(section_id__in=assigned_section_ids(user))
        if user.role in (Role.PARENT, Role.STUDENT):
            return queryset.filter(student__in=visible_students(user, Student.objects.filter(school=user.school)))
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        try:
            if params.get("student"):
                queryset = queryset.filter(student_id=params["student"])
            if params.get("section"):
                queryset = queryset.filter(section_id=params["section"])
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc
        if params.get("date_from"):
            queryset = queryset.filter(date__gte=_date_param(self.request, "date_from"))
        if params.get("date_to"):
            queryset = queryset.filter(date__lte=_date_param(self.request, "date_to"))
        return queryset.order_by("-date", "student__first_name")


class AttendanceMonthlyView(TenantAPIView):
    """Monthly summary + percentage, per section (admin/teacher/receptionist) or per student (also parents/students)."""

    required_permission = P.ATTENDANCE_STUDENTS_VIEW

    def get(self, request):
        month = request.query_params.get("month") or date.today().strftime("%Y-%m")
        queryset = scoped_attendance(request.user)
        try:
            if request.query_params.get("student"):
                queryset = queryset.filter(student_id=request.query_params["student"])
            elif request.query_params.get("section"):
                queryset = queryset.filter(section_id=request.query_params["section"])
            else:
                raise ValidationError({"detail": ["Provide a student or a section."]})
            return success_response(StudentAttendanceService.monthly(queryset=queryset, month=month), message="")
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc


class TeacherAttendanceView(TenantAPIView):
    """Daily teacher attendance sheet (School Admin and Receptionist)."""

    permission_map = {"get": P.ATTENDANCE_TEACHERS_MANAGE, "post": P.ATTENDANCE_TEACHERS_MANAGE}

    def get(self, request):
        day = _date_param(request, "date", default=date.today())
        return success_response(TeacherAttendanceService.roster(school=self.get_school(), day=day), message="")

    def post(self, request):
        serializer = MarkTeachersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        saved = TeacherAttendanceService.mark(
            school=self.get_school(), user=request.user, day=data["date"], records=[dict(r) for r in data["records"]]
        )
        return success_response({"saved": saved}, message="Attendance saved.")


class TeacherAttendanceRecordViewSet(mixins.ListModelMixin, TenantScopedViewSet):
    queryset = TeacherAttendance.objects.select_related("teacher")
    serializer_class = TeacherAttendanceSerializer
    permission_map = {"list": P.ATTENDANCE_TEACHERS_VIEW}

    def scope_queryset(self, queryset):
        user = self.request.user
        return queryset.filter(teacher__user=user) if user.role == Role.TEACHER else queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("date_from"):
            queryset = queryset.filter(date__gte=_date_param(self.request, "date_from"))
        if params.get("date_to"):
            queryset = queryset.filter(date__lte=_date_param(self.request, "date_to"))
        return queryset.order_by("-date", "teacher__first_name")
