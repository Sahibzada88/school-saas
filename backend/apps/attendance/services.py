import calendar
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academics.models import Enrollment, EnrollmentStatus
from apps.academics.scope import can_access_section
from apps.accounts.roles import Role
from apps.teachers.models import Teacher, TeacherStatus

from .models import AttendanceStatus, StudentAttendance, TeacherAttendance
from .alerts import notify_absences
from .stats import attendance_percentage

TEACHER_EDIT_WINDOW_DAYS = 7  # teachers may correct attendance for today and the previous 7 days; admins any past date
MAX_RECORDS = 300


def _require_not_future(day: date) -> None:
    if day > date.today():
        raise ValidationError({"date": ["Attendance cannot be marked for a future date."]})


class StudentAttendanceService:
    @staticmethod
    def _authorize(user, section, day: date) -> None:
        if not can_access_section(user, section.id):
            raise PermissionDenied("You are not assigned to this section.")
        _require_not_future(day)
        if user.role == Role.TEACHER and day < date.today() - timedelta(days=TEACHER_EDIT_WINDOW_DAYS):
            raise PermissionDenied(f"Teachers can only edit attendance from the last {TEACHER_EDIT_WINDOW_DAYS} days.")

    @staticmethod
    def roster(*, user, section, day: date) -> list[dict]:
        if not can_access_section(user, section.id):
            raise PermissionDenied("You are not assigned to this section.")
        enrollments = (
            Enrollment.objects.filter(section=section, session__is_current=True, status=EnrollmentStatus.ENROLLED)
            .select_related("student").order_by("roll_number", "student__first_name")
        )
        marks = {a.student_id: a for a in StudentAttendance.objects.filter(section=section, date=day)}
        return [
            {
                "student": str(e.student_id), "student_name": e.student.full_name, "student_number": e.student.student_number,
                "roll_number": e.roll_number, "status": marks[e.student_id].status if e.student_id in marks else None,
                "remarks": marks[e.student_id].remarks if e.student_id in marks else "",
            }
            for e in enrollments
        ]

    @staticmethod
    @transaction.atomic
    def mark(*, school, user, section, day: date, records: list[dict]) -> int:
        StudentAttendanceService._authorize(user, section, day)
        if len(records) > MAX_RECORDS:
            raise ValidationError({"records": [f"At most {MAX_RECORDS} records per request."]})
        enrollments = {
            str(e.student_id): e
            for e in Enrollment.objects.filter(section=section, session__is_current=True, status=EnrollmentStatus.ENROLLED)
        }
        seen, rows = set(), []
        for record in records:
            key = str(record["student"])
            enrollment = enrollments.get(key)
            if enrollment is None:
                raise ValidationError({"records": ["A student in the request is not enrolled in this section."]})
            if key in seen:
                raise ValidationError({"records": ["A student appears more than once."]})
            seen.add(key)
            rows.append(StudentAttendance(
                school=school, student_id=enrollment.student_id, enrollment=enrollment, section=section, date=day,
                status=record["status"], remarks=record.get("remarks", ""), marked_by=user,
            ))
        StudentAttendance.objects.bulk_create(
            rows, update_conflicts=True, unique_fields=["student", "date"],
            update_fields=["status", "remarks", "marked_by", "section", "enrollment", "updated_at"],
        )
        absent_ids = [r.student_id for r in rows if r.status == AttendanceStatus.ABSENT]
        if absent_ids and day == date.today():
            transaction.on_commit(lambda: notify_absences(school, absent_ids, day))  # after commit: never poisons the save
        return len(rows)

    @staticmethod
    def monthly(*, queryset, month: str) -> dict:
        """queryset: StudentAttendance rows already scoped by the caller. month: YYYY-MM."""
        try:
            year, mon = (int(part) for part in month.split("-"))
            first, last = date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])
        except (ValueError, IndexError) as exc:
            raise ValidationError({"month": ["Use YYYY-MM."]}) from exc
        rows = (
            queryset.filter(date__gte=first, date__lte=last).order_by().values("student_id", "student__first_name", "student__last_name", "student__student_number")
            .annotate(
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id", filter=Q(status=AttendanceStatus.ABSENT)),
                late=Count("id", filter=Q(status=AttendanceStatus.LATE)),
                leave=Count("id", filter=Q(status=AttendanceStatus.LEAVE)),
            ).order_by("student__first_name", "student__last_name")
        )
        students = [
            {
                "student": str(r["student_id"]), "student_name": f"{r['student__first_name']} {r['student__last_name']}".strip(),
                "student_number": r["student__student_number"], "present": r["present"], "absent": r["absent"],
                "late": r["late"], "leave": r["leave"], "percentage": attendance_percentage(r["present"], r["late"], r["absent"]),
            }
            for r in rows
        ]
        return {"month": month, "from": first.isoformat(), "to": last.isoformat(), "students": students}


class TeacherAttendanceService:
    @staticmethod
    def roster(*, school, day: date) -> list[dict]:
        marks = {a.teacher_id: a for a in TeacherAttendance.objects.filter(school=school, date=day)}
        teachers = Teacher.objects.filter(school=school, status=TeacherStatus.ACTIVE).order_by("first_name", "last_name")
        return [
            {
                "teacher": str(t.id), "teacher_name": t.full_name, "employee_id": t.employee_id,
                "status": marks[t.id].status if t.id in marks else None,
                "check_in": marks[t.id].check_in if t.id in marks else None,
                "check_out": marks[t.id].check_out if t.id in marks else None,
                "remarks": marks[t.id].remarks if t.id in marks else "",
            }
            for t in teachers
        ]

    @staticmethod
    @transaction.atomic
    def mark(*, school, user, day: date, records: list[dict]) -> int:
        _require_not_future(day)
        valid = set(str(i) for i in Teacher.objects.filter(school=school).values_list("id", flat=True))
        rows, seen = [], set()
        for record in records:
            key = str(record["teacher"])
            if key not in valid or key in seen:
                raise ValidationError({"records": ["Unknown or repeated teacher in the request."]})
            seen.add(key)
            rows.append(TeacherAttendance(
                school=school, teacher_id=key, date=day, status=record["status"], check_in=record.get("check_in"),
                check_out=record.get("check_out"), remarks=record.get("remarks", ""), marked_by=user,
            ))
        TeacherAttendance.objects.bulk_create(
            rows, update_conflicts=True, unique_fields=["teacher", "date"],
            update_fields=["status", "check_in", "check_out", "remarks", "marked_by", "updated_at"],
        )
        return len(rows)


def today_summary(school) -> dict:
    """For the School Admin dashboard: today's student attendance, from real rows."""
    today = date.today()
    counts = dict.fromkeys(AttendanceStatus.values, 0)
    for row in StudentAttendance.objects.filter(school=school, date=today).order_by().values("status").annotate(c=Count("id")):
        counts[row["status"]] = row["c"]
    enrolled = Enrollment.objects.filter(school=school, session__is_current=True, status=EnrollmentStatus.ENROLLED).count()
    marked = sum(counts.values())
    return {"date": today.isoformat(), "enrolled": enrolled, "marked": marked, "counts": counts,
            "percentage": attendance_percentage(counts["PRESENT"], counts["LATE"], counts["ABSENT"])}
