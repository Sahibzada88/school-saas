from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum

from apps.academics.models import SchoolClass
from apps.accounts.models import User
from apps.accounts.roles import Role, SCHOOL_ROLES
from apps.audit_logs.models import AuditLog
from apps.audit_logs.serializers import SchoolAuditLogSerializer


def build_school_dashboard(school) -> dict:
    """Real, tenant-scoped numbers only. Students, attendance, fees and subscription widgets are added by the
    phases that introduce those models (5-9, 4)."""
    users = User.objects.filter(school=school)
    by_role = dict.fromkeys(SCHOOL_ROLES, 0)
    for row in users.order_by().values("role").annotate(count=Count("id")):
        by_role[row["role"]] = row["count"]

    from apps.attendance.services import today_summary
    from apps.examinations.models import Exam, ExamStatus
    from apps.fees.models import InvoiceStatus, StudentInvoice
    from apps.students.models import Student, StudentStatus
    from apps.teachers.models import Teacher, TeacherStatus

    students = Student.objects.filter(school=school)
    teachers = Teacher.objects.filter(school=school)
    open_invoices = StudentInvoice.objects.filter(school=school, status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID], balance__gt=0)
    outstanding = open_invoices.aggregate(total=Sum("balance"))["total"] or Decimal("0")
    upcoming = Exam.objects.filter(school=school, status__in=[ExamStatus.SCHEDULED, ExamStatus.MARKS_ENTRY]).order_by("start_date", "name")[:5]
    recent = AuditLog.objects.filter(school=school).select_related("actor").order_by("-created_at")[:8]
    return {
        "school": {
            "name": school.name,
            "status": school.status,
            "city": school.city,
            "country": school.country,
            "created_at": school.created_at,
        },
        "users": {
            "total": sum(by_role.values()),
            "active": users.filter(is_active=True).count(),
            "by_role": by_role,
        },
        "students": {"total": students.count(), "active": students.filter(status=StudentStatus.ACTIVE).count()},
        "teachers": {"total": teachers.count(), "active": teachers.filter(status=TeacherStatus.ACTIVE).count()},
        "attendance_today": today_summary(school),
        "fees": {
            "outstanding_total": f"{outstanding:.2f}", "outstanding_count": open_invoices.count(),
            "overdue_count": open_invoices.filter(due_date__lt=date.today()).count(), "currency": school.currency,
        },
        "upcoming_exams": [{"id": str(e.id), "name": e.name, "start_date": e.start_date, "status": e.status} for e in upcoming],
        "checklist": [
            {"key": "profile", "label": "Complete your school profile", "done": bool(school.phone and school.address)},
            {"key": "team", "label": "Add your team members", "done": users.exclude(role=Role.SCHOOL_ADMIN).exists()},
            {"key": "classes", "label": "Create your classes and sections", "done": SchoolClass.objects.filter(school=school).exists()},
            {"key": "teachers", "label": "Add your teachers", "done": teachers.exists()},
            {"key": "students", "label": "Admit your students", "done": students.exists()},
        ],
        "recent_activity": SchoolAuditLogSerializer(recent, many=True).data,
    }
