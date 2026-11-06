from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict
from apps.core.numbering import format_number, next_number
from apps.subscriptions.limits import enforce_plan_limit
from apps.tenants.images import ImageService

from .models import Guardian, Student, StudentGuardian, StudentStatus


def _active_count(school) -> int:
    return Student.objects.filter(school=school, status=StudentStatus.ACTIVE).count()


class StudentService:
    @staticmethod
    @transaction.atomic
    def admit(*, school, data: dict, actor, request) -> Student:
        enforce_plan_limit(school, "students", _active_count(school))
        data = dict(data)
        photo = data.pop("photo", None)
        number = format_number(school.settings.student_number_prefix, next_number(school, "STUDENT"))
        student = Student.objects.create(
            school=school, student_number=number, admission_date=data.pop("admission_date", None) or date.today(),
            photo=ImageService.store(school, photo) if photo else None, **data,
        )
        AuditService.record(
            AuditAction.STUDENT_CREATED, actor=actor, school=school, entity_type="student", entity_id=student.id,
            description=f"Admitted {student.full_name} ({student.student_number})", request=request,
        )
        return student

    @staticmethod
    @transaction.atomic
    def update(*, student: Student, data: dict, actor, request) -> Student:
        data = dict(data)
        if "photo" in data:
            student.photo = ImageService.replace(student.school, student.photo, data.pop("photo"))
        for field, value in data.items():
            setattr(student, field, value)
        student.save()
        AuditService.record(
            AuditAction.STUDENT_UPDATED, actor=actor, school=student.school, entity_type="student", entity_id=student.id,
            description=f"Updated {student.full_name}", metadata={"fields": sorted(data.keys())}, request=request,
        )
        return student

    @staticmethod
    @transaction.atomic
    def change_status(*, student: Student, status: str, reason: str, actor, request) -> Student:
        if student.status == status:
            raise Conflict(f"The student is already {status.lower()}.", code="invalid_transition")
        if status == StudentStatus.ACTIVE:
            enforce_plan_limit(student.school, "students", _active_count(student.school))
        previous = student.status
        student.status, student.status_changed_at = status, timezone.now()
        student.save(update_fields=["status", "status_changed_at", "updated_at"])
        if status in (StudentStatus.TRANSFERRED, StudentStatus.GRADUATED, StudentStatus.INACTIVE):
            from apps.academics.services import EnrollmentService

            EnrollmentService.end_current_enrollment(student, status)
        AuditService.record(
            AuditAction.STUDENT_STATUS_CHANGED, actor=actor, school=student.school, entity_type="student", entity_id=student.id,
            description=f"{student.full_name}: {previous} -> {status}" + (f" ({reason})" if reason else ""),
            metadata={"from": previous, "to": status, "reason": reason}, request=request,
        )
        return student

    @staticmethod
    @transaction.atomic
    def delete(*, student: Student, actor, request) -> None:
        AuditService.record(
            AuditAction.STUDENT_DELETED, actor=actor, school=student.school, entity_type="student", entity_id=student.id,
            description=f"Deleted {student.full_name} ({student.student_number})", request=request,
        )
        student.delete()  # soft delete: the row, enrollments, marks and invoices are kept

    # ------------------------------------------------------------------ guardians
    @staticmethod
    @transaction.atomic
    def link_guardian(*, student: Student, data: dict, actor, request) -> StudentGuardian:
        guardian = data.get("guardian")
        if guardian is None:
            guardian = Guardian.objects.create(school=student.school, **data["new_guardian"])
        if StudentGuardian.objects.filter(student=student, guardian=guardian).exists():
            raise ValidationError({"guardian": ["This guardian is already linked to the student."]})
        if data["is_primary"]:
            StudentGuardian.objects.filter(student=student, is_primary=True).update(is_primary=False)
        link = StudentGuardian.objects.create(
            school=student.school, student=student, guardian=guardian, relationship=data["relationship"],
            is_primary=data["is_primary"], is_emergency_contact=data["is_emergency_contact"],
        )
        AuditService.record(
            AuditAction.GUARDIAN_LINKED, actor=actor, school=student.school, entity_type="student", entity_id=student.id,
            description=f"Linked {guardian.full_name} to {student.full_name}", request=request,
        )
        return link

    @staticmethod
    @transaction.atomic
    def unlink_guardian(*, link: StudentGuardian, actor, request) -> None:
        AuditService.record(
            AuditAction.GUARDIAN_UNLINKED, actor=actor, school=link.school, entity_type="student", entity_id=link.student_id,
            description=f"Unlinked {link.guardian.full_name} from {link.student.full_name}", request=request,
        )
        link.delete()
