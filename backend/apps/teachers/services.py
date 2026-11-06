from datetime import date

from django.db import transaction

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.numbering import format_number, next_number
from apps.subscriptions.limits import enforce_plan_limit
from apps.tenants.images import ImageService

from .models import Teacher, TeacherStatus


class TeacherService:
    @staticmethod
    @transaction.atomic
    def create(*, school, data: dict, actor, request) -> Teacher:
        enforce_plan_limit(school, "teachers", Teacher.objects.filter(school=school, status=TeacherStatus.ACTIVE).count())
        data = dict(data)
        photo = data.pop("photo", None)
        employee_id = format_number("EMP", next_number(school, "EMPLOYEE"), width=4)
        teacher = Teacher.objects.create(
            school=school, employee_id=employee_id, joining_date=data.pop("joining_date", None) or date.today(),
            photo=ImageService.store(school, photo) if photo else None, **data,
        )
        AuditService.record(
            AuditAction.TEACHER_CREATED, actor=actor, school=school, entity_type="teacher", entity_id=teacher.id,
            description=f"Added teacher {teacher.full_name} ({employee_id})", request=request,
        )
        return teacher

    @staticmethod
    @transaction.atomic
    def update(*, teacher: Teacher, data: dict, actor, request) -> Teacher:
        data = dict(data)
        if "photo" in data:
            teacher.photo = ImageService.replace(teacher.school, teacher.photo, data.pop("photo"))
        for field, value in data.items():
            setattr(teacher, field, value)
        teacher.save()
        AuditService.record(
            AuditAction.TEACHER_UPDATED, actor=actor, school=teacher.school, entity_type="teacher", entity_id=teacher.id,
            description=f"Updated {teacher.full_name}", metadata={"fields": sorted(data.keys())}, request=request,
        )
        return teacher

    @staticmethod
    @transaction.atomic
    def delete(*, teacher: Teacher, actor, request) -> None:
        AuditService.record(
            AuditAction.TEACHER_DELETED, actor=actor, school=teacher.school, entity_type="teacher", entity_id=teacher.id,
            description=f"Deleted teacher {teacher.full_name}", request=request,
        )
        teacher.delete()
