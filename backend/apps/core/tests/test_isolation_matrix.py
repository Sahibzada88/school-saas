"""Automated tenant-isolation matrix.

Every TenantScopedViewSet MUST have an entry in ISOLATION_CASES (a guard test fails otherwise).
For every case: School A cannot list, read or modify School B's object (404, never 200) and nothing from B appears
in A's list. Exports and PDFs are covered separately in apps/reports/tests."""
from dataclasses import dataclass
from datetime import date, time
from typing import Callable

import config.urls  # noqa: F401  (imports every routed viewset so the registry is populated)
from django.test import TestCase

from apps.accounts.roles import Role
from apps.accounts.school_user_views import SchoolUserViewSet
from apps.academics import views as academics
from apps.attendance import views as attendance
from apps.attendance.models import StudentAttendance, TeacherAttendance
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.audit_logs.views import SchoolAuditLogViewSet
from apps.core import factories as f
from apps.core.testing import login_client, make_school, make_user
from apps.core.viewsets import TenantScopedViewSet
from apps.examinations import views as exams
from apps.fees import views as fees
from apps.students import views as students
from apps.teachers.views import TeacherViewSet
from apps.notifications.announcements import AnnouncementViewSet


@dataclass
class IsolationCase:
    list_url: str
    detail_url: str | None
    create_object: Callable
    write_methods: tuple = ("patch",)
    write_payload: dict | None = None


def _student_with_enrollment(school):
    student = f.make_student(school)
    section = f.make_section(f.make_class(school))
    return student, section, f.enroll(student, section)


def _attendance(school):
    student, section, enrollment = _student_with_enrollment(school)
    return StudentAttendance.objects.create(school=school, student=student, enrollment=enrollment, section=section, date=date.today(), status="PRESENT")


def _teacher_attendance(school):
    return TeacherAttendance.objects.create(school=school, teacher=f.make_teacher(school), date=date.today(), status="PRESENT")


def _exam_subject(school):
    exam = f.make_exam(school)
    return f.make_exam_subject(exam, f.make_class(school), f.make_subject(school))


def _report_card(school):
    exam = f.make_exam(school)
    student, _, enrollment = _student_with_enrollment(school)
    return f.make_report_card(exam, student, enrollment)


def _structure(school):
    from apps.fees.models import FeeStructure

    return FeeStructure.objects.create(school=school, session=f.current_session(school), name="Monthly")


def _invoice(school):
    student, _, enrollment = _student_with_enrollment(school)
    return f.make_invoice(student, enrollment)


def _payment(school):
    return f.make_fee_payment(_invoice(school))


def _grading_scale(school):
    from apps.examinations.models import GradingScale

    return GradingScale.objects.create(school=school, name=f"Scale {school.id.hex[:4]}")


def _exam_type(school):
    from apps.examinations.models import ExamType

    return ExamType.objects.create(school=school, name=f"Type {school.id.hex[:4]}")


def _fee_category(school):
    from apps.fees.models import FeeCategory

    return FeeCategory.objects.create(school=school, name="Lab", code=f"L{school.id.hex[:4]}")


def _class_subject(school):
    from apps.academics.models import ClassSubject

    return ClassSubject.objects.create(school=school, school_class=f.make_class(school), subject=f.make_subject(school))


def _assignment(school):
    section = f.make_section(f.make_class(school))
    return f.assign_teacher(f.make_teacher(school), section)


def _timetable(school):
    from apps.academics.models import TimetableSlot

    section = f.make_section(f.make_class(school))
    return TimetableSlot.objects.create(
        school=school, session=f.current_session(school), section=section, subject=f.make_subject(school), teacher=f.make_teacher(school),
        weekday=0, period_no=1, start_time=time(8, 0), end_time=time(8, 40),
    )


def _student_document(school):
    from apps.students.models import StudentDocument

    return StudentDocument.objects.create(school=school, student=f.make_student(school), doc_type="B-Form", title="Birth certificate")


U = "/api/v1/school"
ISOLATION_CASES: dict[type, IsolationCase] = {
    SchoolUserViewSet: IsolationCase(f"{U}/users/", f"{U}/users/{{id}}/", lambda s: make_user(s, Role.TEACHER), write_payload={"first_name": "Hacked"}),
    SchoolAuditLogViewSet: IsolationCase(f"{U}/audit-logs/", f"{U}/audit-logs/{{id}}/", lambda s: AuditService.record(AuditAction.USER_UPDATED, school=s, description="matrix"), write_methods=()),
    students.StudentViewSet: IsolationCase(f"{U}/students/", f"{U}/students/{{id}}/", f.make_student, write_payload={"first_name": "Hacked"}),
    students.GuardianViewSet: IsolationCase(f"{U}/guardians/", f"{U}/guardians/{{id}}/", f.make_guardian, write_payload={"first_name": "Hacked"}),
    students.StudentDocumentViewSet: IsolationCase(f"{U}/student-documents/", f"{U}/student-documents/{{id}}/", _student_document, write_payload={"title": "Hacked"}),
    TeacherViewSet: IsolationCase(f"{U}/teachers/", f"{U}/teachers/{{id}}/", f.make_teacher, write_payload={"first_name": "Hacked"}),
    academics.AcademicSessionViewSet: IsolationCase(f"{U}/sessions/", f"{U}/sessions/{{id}}/", f.make_session, write_payload={"name": "Hacked"}),
    academics.SchoolClassViewSet: IsolationCase(f"{U}/classes/", f"{U}/classes/{{id}}/", f.make_class, write_payload={"name": "Hacked"}),
    academics.SectionViewSet: IsolationCase(f"{U}/sections/", f"{U}/sections/{{id}}/", lambda s: f.make_section(f.make_class(s)), write_payload={"name": "Hacked"}),
    academics.SubjectViewSet: IsolationCase(f"{U}/subjects/", f"{U}/subjects/{{id}}/", f.make_subject, write_payload={"name": "Hacked"}),
    academics.ClassSubjectViewSet: IsolationCase(f"{U}/class-subjects/", f"{U}/class-subjects/{{id}}/", _class_subject, write_payload={"is_optional": True}),
    academics.TeacherAssignmentViewSet: IsolationCase(f"{U}/teacher-assignments/", f"{U}/teacher-assignments/{{id}}/", _assignment, write_payload={"is_class_teacher": True}),
    academics.EnrollmentViewSet: IsolationCase(f"{U}/enrollments/", f"{U}/enrollments/{{id}}/", lambda s: _student_with_enrollment(s)[2], write_payload={"roll_number": 99}),
    academics.TimetableSlotViewSet: IsolationCase(f"{U}/timetable/", f"{U}/timetable/{{id}}/", _timetable, write_payload={"room": "Hacked"}),
    attendance.AttendanceRecordViewSet: IsolationCase(f"{U}/attendance/records/", None, _attendance, write_methods=()),
    attendance.TeacherAttendanceRecordViewSet: IsolationCase(f"{U}/attendance/teacher-records/", None, _teacher_attendance, write_methods=()),
    exams.ExamTypeViewSet: IsolationCase(f"{U}/exam-types/", f"{U}/exam-types/{{id}}/", _exam_type, write_payload={"name": "Hacked"}),
    exams.GradingScaleViewSet: IsolationCase(f"{U}/grading-scales/", f"{U}/grading-scales/{{id}}/", _grading_scale, write_payload={"name": "Hacked"}),
    exams.ExamViewSet: IsolationCase(f"{U}/exams/", f"{U}/exams/{{id}}/", f.make_exam, write_payload={"name": "Hacked"}),
    exams.ExamSubjectViewSet: IsolationCase(f"{U}/exam-subjects/", f"{U}/exam-subjects/{{id}}/", _exam_subject, write_payload={"total_marks": "50"}),
    exams.ResultViewSet: IsolationCase(f"{U}/results/", f"{U}/results/{{id}}/", _report_card, write_methods=()),
    fees.FeeCategoryViewSet: IsolationCase(f"{U}/fees/categories/", f"{U}/fees/categories/{{id}}/", _fee_category, write_payload={"name": "Hacked"}),
    fees.FeeStructureViewSet: IsolationCase(f"{U}/fees/structures/", f"{U}/fees/structures/{{id}}/", _structure, write_payload={"name": "Hacked"}),
    fees.InvoiceViewSet: IsolationCase(f"{U}/fees/invoices/", f"{U}/fees/invoices/{{id}}/", _invoice, write_methods=()),
    fees.FeePaymentViewSet: IsolationCase(f"{U}/fees/payments/", f"{U}/fees/payments/{{id}}/", _payment, write_methods=()),
    AnnouncementViewSet: IsolationCase(f"{U}/announcements/", f"{U}/announcements/{{id}}/", f.make_announcement, write_payload={"title": "Hacked"}),
}


class IsolationMatrixTests(TestCase):
    def test_every_tenant_viewset_has_an_isolation_case(self):
        missing = [v.__name__ for v in TenantScopedViewSet.registry if v not in ISOLATION_CASES]
        self.assertEqual(missing, [], "Add the viewset to ISOLATION_CASES.")

    def test_school_a_cannot_touch_school_b(self):
        school_a, school_b = make_school("Matrix A"), make_school("Matrix B")
        admin = make_user(school_a, Role.SCHOOL_ADMIN)
        client = login_client(admin)
        for viewset, case in ISOLATION_CASES.items():
            with self.subTest(viewset=viewset.__name__):
                own = case.create_object(school_a)
                foreign = case.create_object(school_b)

                response = client.get(case.list_url + "?page_size=100")
                self.assertEqual(response.status_code, 200, response.content)
                listed = {str(row["id"]) for row in response.json()["data"]["results"]}
                self.assertIn(str(own.id), listed)
                self.assertNotIn(str(foreign.id), listed)

                if case.detail_url:
                    detail = case.detail_url.format(id=foreign.id)
                    self.assertEqual(client.get(detail).status_code, 404)
                    for method in case.write_methods:
                        self.assertEqual(getattr(client, method)(detail, case.write_payload or {}).status_code, 404, method)
                    self.assertEqual(client.get(case.detail_url.format(id=own.id)).status_code, 200)
