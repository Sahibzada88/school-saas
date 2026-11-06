from datetime import date

from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.academics.models import Enrollment, EnrollmentStatus, Section
from apps.academics.scope import current_session
from apps.academics.services import EnrollmentService
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.csv_import import ImportReport, read_csv_rows
from apps.core.validators import validate_phone_number
from apps.subscriptions.limits import enforce_plan_limit

from .models import Guardian, Relationship, Student, StudentStatus
from .serializers import StudentWriteSerializer
from .services import StudentService

REQUIRED = ["first_name", "date_of_birth", "gender"]
TEMPLATE_HEADER = ["first_name", "last_name", "date_of_birth", "gender", "phone", "email", "address", "blood_group", "class", "section", "guardian_name", "guardian_phone", "guardian_relationship"]
TEMPLATE_ROWS = [
    ["Ali", "Khan", "2012-05-01", "MALE", "", "", "Lahore", "B+", "10", "A", "Ahmed Khan", "+92 300 1234567", "FATHER"],
    ["Sara", "Khan", "2013-09-15", "FEMALE", "", "", "Lahore", "", "9", "A", "Ahmed Khan", "+92 300 1234567", "FATHER"],
]
GENDERS = {"m": "MALE", "male": "MALE", "f": "FEMALE", "female": "FEMALE", "o": "OTHER", "other": "OTHER"}


class _Abort(Exception):
    def __init__(self, row: int, message: str):
        self.row, self.message = row, message


class StudentImportService:
    @staticmethod
    def run(*, school, uploaded, dry_run: bool, actor, request) -> dict:
        rows = read_csv_rows(uploaded, REQUIRED)
        report = ImportReport(total=len(rows), dry_run=dry_run)

        sections = {(s.school_class.name.lower(), s.name.lower()): s for s in Section.objects.filter(school=school).select_related("school_class")}
        session = current_session(school)
        existing = {(s.first_name.lower(), s.last_name.lower(), s.date_of_birth) for s in Student.objects.filter(school=school)}
        planned, seen, capacity_used = [], set(), {}

        for number, row in rows:
            payload = {
                "first_name": row.get("first_name", ""), "last_name": row.get("last_name", ""), "date_of_birth": row.get("date_of_birth", ""),
                "gender": GENDERS.get(row.get("gender", "").lower(), row.get("gender", "").upper()), "phone": row.get("phone", ""),
                "email": row.get("email", ""), "address": row.get("address", ""), "blood_group": row.get("blood_group", ""),
            }
            serializer = StudentWriteSerializer(data=payload)
            if not serializer.is_valid():
                for field_name, messages in serializer.errors.items():
                    report.add_error(number, f"{field_name}: {' '.join(str(m) for m in messages)}")
                continue
            data = dict(serializer.validated_data)
            key = (data["first_name"].lower(), data.get("last_name", "").lower(), data["date_of_birth"])
            if key in seen:
                report.add_error(number, "This student appears twice in the file.")
            elif key in existing:
                report.add_error(number, "A student with the same name and date of birth already exists.")
            seen.add(key)

            section = None
            class_name, section_name = row.get("class", ""), row.get("section", "")
            if class_name or section_name:
                if not (class_name and section_name):
                    report.add_error(number, "Give both class and section, or leave both empty.")
                elif session is None:
                    report.add_error(number, "There is no current academic session to enrol into.")
                else:
                    section = sections.get((class_name.lower(), section_name.lower()))
                    if section is None:
                        report.add_error(number, f"Section '{class_name}-{section_name}' does not exist.")
            if section is not None:
                used = capacity_used.setdefault(section.id, Enrollment.objects.filter(section=section, session=session, status=EnrollmentStatus.ENROLLED).count())
                if section.capacity is not None and used >= section.capacity:
                    report.add_error(number, f"Section {class_name}-{section_name} is full (capacity {section.capacity}).")
                capacity_used[section.id] = used + 1

            guardian = None
            g_name, g_phone = row.get("guardian_name", ""), row.get("guardian_phone", "")
            if g_name or g_phone:
                relationship = (row.get("guardian_relationship") or "GUARDIAN").upper()
                if not (g_name and g_phone):
                    report.add_error(number, "Give both guardian_name and guardian_phone, or leave both empty.")
                elif relationship not in Relationship.values:
                    report.add_error(number, f"guardian_relationship must be one of {', '.join(Relationship.values)}.")
                else:
                    try:
                        guardian = {"name": g_name, "phone": validate_phone_number(g_phone), "relationship": relationship}
                    except Exception:
                        report.add_error(number, "guardian_phone is not a valid phone number.")
            planned.append((number, data, section, guardian))

        if report.errors or dry_run:
            return report.as_dict()

        active = Student.objects.filter(school=school, status=StudentStatus.ACTIVE).count()
        enforce_plan_limit(school, "students", active + len(planned) - 1)  # raises 403 plan_limit_reached for the whole file
        try:
            with transaction.atomic():
                guardians_cache: dict = {}
                for number, data, section, guardian in planned:
                    try:
                        student = StudentService.admit(school=school, data={**data, "admission_date": date.today()}, actor=actor, request=request)
                        if guardian:
                            cache_key = (guardian["name"].lower(), guardian["phone"])
                            record = guardians_cache.get(cache_key) or Guardian.objects.filter(school=school, phone=guardian["phone"], first_name__iexact=guardian["name"].split(" ")[0]).first()
                            if record is None:
                                first, _, last = guardian["name"].partition(" ")
                                record = Guardian.objects.create(school=school, first_name=first, last_name=last, phone=guardian["phone"])
                            guardians_cache[cache_key] = record
                            StudentService.link_guardian(
                                student=student, actor=actor, request=request,
                                data={"guardian": record, "relationship": guardian["relationship"], "is_primary": True, "is_emergency_contact": False},
                            )
                        if section is not None:
                            EnrollmentService.enroll(school=school, student=student, session=session, section=section, roll_number=None, actor=actor, request=request)
                    except (APIException, ValidationError) as exc:
                        raise _Abort(number, str(getattr(exc, "detail", exc))) from exc
                    report.created += 1
        except _Abort as abort:
            report.created = 0
            report.add_error(abort.row, abort.message)
            return report.as_dict()
        AuditService.record(
            AuditAction.STUDENTS_IMPORTED, actor=actor, school=school, entity_type="student", entity_id="import",
            description=f"Imported {report.created} student(s) from CSV", metadata={"created": report.created}, request=request,
        )
        return report.as_dict()
