from datetime import date

from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.csv_import import ImportReport, read_csv_rows
from apps.subscriptions.limits import enforce_plan_limit

from .models import Teacher, TeacherStatus
from .serializers import TeacherWriteSerializer
from .services import TeacherService

REQUIRED = ["first_name", "gender"]
TEMPLATE_HEADER = ["first_name", "last_name", "gender", "phone", "email", "qualification", "joining_date", "date_of_birth", "address"]
TEMPLATE_ROWS = [["Sana", "Ali", "FEMALE", "+92 300 7654321", "sana@example.com", "M.Sc Mathematics", "2025-08-01", "1990-04-12", "Lahore"]]
GENDERS = {"m": "MALE", "male": "MALE", "f": "FEMALE", "female": "FEMALE", "o": "OTHER", "other": "OTHER"}


class _Abort(Exception):
    def __init__(self, row: int, message: str):
        self.row, self.message = row, message


class TeacherImportService:
    @staticmethod
    def run(*, school, uploaded, dry_run: bool, actor, request) -> dict:
        rows = read_csv_rows(uploaded, REQUIRED)
        report = ImportReport(total=len(rows), dry_run=dry_run)
        planned = []
        for number, row in rows:
            payload = {k: row.get(k, "") for k in ("first_name", "last_name", "phone", "email", "address", "qualification")}
            payload["gender"] = GENDERS.get(row.get("gender", "").lower(), row.get("gender", "").upper())
            for optional in ("joining_date", "date_of_birth"):
                if row.get(optional):
                    payload[optional] = row[optional]
            serializer = TeacherWriteSerializer(data=payload)
            if not serializer.is_valid():
                for field_name, messages in serializer.errors.items():
                    report.add_error(number, f"{field_name}: {' '.join(str(m) for m in messages)}")
                continue
            planned.append((number, dict(serializer.validated_data)))
        if report.errors or dry_run:
            return report.as_dict()

        active = Teacher.objects.filter(school=school, status=TeacherStatus.ACTIVE).count()
        enforce_plan_limit(school, "teachers", active + len(planned) - 1)
        try:
            with transaction.atomic():
                for number, data in planned:
                    try:
                        TeacherService.create(school=school, data={**data, "joining_date": data.get("joining_date") or date.today()}, actor=actor, request=request)
                    except (APIException, ValidationError) as exc:
                        raise _Abort(number, str(getattr(exc, "detail", exc))) from exc
                    report.created += 1
        except _Abort as abort:
            report.created = 0
            report.add_error(abort.row, abort.message)
            return report.as_dict()
        AuditService.record(
            AuditAction.TEACHERS_IMPORTED, actor=actor, school=school, entity_type="teacher", entity_id="import",
            description=f"Imported {report.created} teacher(s) from CSV", metadata={"created": report.created}, request=request,
        )
        return report.as_dict()
