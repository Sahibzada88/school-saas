from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Max
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict
from apps.students.models import Student, StudentStatus

from .models import Enrollment, EnrollmentStatus, Section


def _enrolled_count(section, session) -> int:
    return Enrollment.objects.filter(section=section, session=session, status=EnrollmentStatus.ENROLLED).count()


def _check_capacity(section, session) -> None:
    if section.capacity is not None and _enrolled_count(section, session) >= section.capacity:
        raise Conflict(f"Section {section.name} is full (capacity {section.capacity}).", code="section_full")


def _next_roll(section, session) -> int:
    return (Enrollment.objects.filter(section=section, session=session).aggregate(m=Max("roll_number"))["m"] or 0) + 1


class EnrollmentService:
    @staticmethod
    @transaction.atomic
    def enroll(*, school, student: Student, session, section: Section, roll_number, actor, request) -> Enrollment:
        if student.status != StudentStatus.ACTIVE:
            raise ValidationError({"student": ["Only active students can be enrolled."]})
        if Enrollment.objects.filter(student=student, session=session).exists():
            raise Conflict("This student is already enrolled in that session.", code="already_enrolled")
        locked = Section.objects.select_for_update().select_related("school_class").get(pk=section.pk)  # serialises capacity + roll allocation
        _check_capacity(locked, session)
        try:
            enrollment = Enrollment.objects.create(
                school=school, student=student, session=session, school_class_id=locked.school_class_id, section=locked,
                roll_number=roll_number or _next_roll(locked, session), enrolled_on=date.today(),
            )
        except IntegrityError as exc:
            raise ValidationError({"roll_number": ["This roll number is already used in the section."]}) from exc
        AuditService.record(
            AuditAction.STUDENT_ENROLLED, actor=actor, school=school, entity_type="student", entity_id=student.id,
            description=f"Enrolled {student.full_name} in {locked.school_class.name}-{locked.name}", request=request,
        )
        return enrollment

    @staticmethod
    @transaction.atomic
    def move(*, enrollment: Enrollment, section=None, roll_number=None, actor, request) -> Enrollment:
        enrollment = Enrollment.objects.select_for_update().select_related("section__school_class").get(pk=enrollment.pk)
        if enrollment.status != EnrollmentStatus.ENROLLED:
            raise Conflict("Only a current enrollment can be changed.", code="invalid_transition")
        if section is not None and section.id != enrollment.section_id:
            _check_capacity(Section.objects.select_for_update().get(pk=section.pk), enrollment.session)
            enrollment.section, enrollment.school_class_id = section, section.school_class_id
            if roll_number is None:
                roll_number = _next_roll(section, enrollment.session)
        if roll_number is not None:
            enrollment.roll_number = roll_number
        try:
            enrollment.save()
        except IntegrityError as exc:
            raise ValidationError({"roll_number": ["This roll number is already used in the section."]}) from exc
        return enrollment

    @staticmethod
    def end_current_enrollment(student: Student, student_status: str) -> None:
        mapping = {
            StudentStatus.TRANSFERRED: EnrollmentStatus.TRANSFERRED,
            StudentStatus.GRADUATED: EnrollmentStatus.GRADUATED,
            StudentStatus.INACTIVE: EnrollmentStatus.WITHDRAWN,
        }
        Enrollment.objects.filter(student=student, session__is_current=True, status=EnrollmentStatus.ENROLLED).update(
            status=mapping[student_status], ended_on=date.today()
        )

    @staticmethod
    @transaction.atomic
    def promote(*, school, from_session, to_session, promote_to, repeat_to, decisions, actor, request) -> dict:
        counts = {"promoted": 0, "repeated": 0, "graduated": 0}
        for decision in decisions:
            old = Enrollment.objects.select_for_update().select_related("student").get(pk=decision["enrollment"].pk)
            if old.session_id != from_session.id or old.status != EnrollmentStatus.ENROLLED:
                raise ValidationError({"decisions": [f"{old.student.full_name} is not currently enrolled in the source session."]})
            outcome = decision["outcome"]
            if outcome == "GRADUATE":
                old.status, old.ended_on = EnrollmentStatus.GRADUATED, date.today()
                old.save(update_fields=["status", "ended_on", "updated_at"])
                Student.objects.filter(pk=old.student_id).update(status=StudentStatus.GRADUATED)
                counts["graduated"] += 1
                continue
            target = promote_to if outcome == "PROMOTE" else repeat_to
            if Enrollment.objects.filter(student=old.student, session=to_session).exists():
                raise Conflict(f"{old.student.full_name} is already enrolled in the target session.", code="already_enrolled")
            _check_capacity(Section.objects.select_for_update().get(pk=target.pk), to_session)
            old.status = EnrollmentStatus.PROMOTED if outcome == "PROMOTE" else EnrollmentStatus.REPEATED
            old.ended_on = date.today()
            old.save(update_fields=["status", "ended_on", "updated_at"])
            Enrollment.objects.create(
                school=school, student=old.student, session=to_session, school_class_id=target.school_class_id, section=target,
                roll_number=_next_roll(target, to_session), enrolled_on=date.today(), promoted_from=old,
            )
            counts["promoted" if outcome == "PROMOTE" else "repeated"] += 1
        AuditService.record(
            AuditAction.STUDENTS_PROMOTED, actor=actor, school=school, entity_type="session", entity_id=to_session.id,
            description=f"Year-end processing {from_session.name} -> {to_session.name}: {counts}", metadata=counts, request=request,
        )
        return counts
