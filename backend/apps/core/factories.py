"""Test factories for tenant data. They bypass services on purpose (fast, explicit state)."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone


def _n() -> str:
    return uuid4().hex[:6]


def make_student(school, **kw):
    from apps.students.models import Student

    n = _n()
    defaults = dict(student_number=f"T-{n}", admission_date=date(2026, 1, 5), first_name="Ali", last_name=f"Khan{n}", date_of_birth=date(2012, 3, 4), gender="MALE")
    return Student.objects.create(school=school, **{**defaults, **kw})


def make_guardian(school, **kw):
    from apps.students.models import Guardian

    defaults = dict(first_name="Ahmed", last_name=f"Khan{_n()}", phone="+92 300 1234567")
    return Guardian.objects.create(school=school, **{**defaults, **kw})


def link_guardian(student, guardian, **kw):
    from apps.students.models import StudentGuardian

    return StudentGuardian.objects.create(school=student.school, student=student, guardian=guardian, **kw)


def make_teacher(school, **kw):
    from apps.teachers.models import Teacher

    defaults = dict(employee_id=f"E-{_n()}", first_name="Sana", last_name=f"Ali{_n()}", gender="FEMALE", joining_date=date(2025, 8, 1))
    return Teacher.objects.create(school=school, **{**defaults, **kw})


def current_session(school):
    from apps.academics.models import AcademicSession

    session = AcademicSession.objects.filter(school=school, is_current=True).first()
    if session is None:
        session = AcademicSession.objects.create(school=school, name=f"S{_n()}", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_current=True)
    return session


def make_session(school, **kw):
    from apps.academics.models import AcademicSession

    defaults = dict(name=f"S{_n()}", start_date=date(2027, 1, 1), end_date=date(2027, 12, 31), is_current=False)
    return AcademicSession.objects.create(school=school, **{**defaults, **kw})


def make_class(school, **kw):
    from apps.academics.models import SchoolClass

    defaults = dict(name=f"C{_n()}", level_order=1)
    return SchoolClass.objects.create(school=school, **{**defaults, **kw})


def make_section(school_class, name="A", **kw):
    from apps.academics.models import Section

    return Section.objects.create(school=school_class.school, school_class=school_class, name=name, **kw)


def make_subject(school, **kw):
    from apps.academics.models import Subject

    n = _n()
    defaults = dict(name=f"Subject {n}", code=f"S{n}".upper())
    return Subject.objects.create(school=school, **{**defaults, **kw})


def enroll(student, section, session=None, **kw):
    from apps.academics.models import Enrollment

    defaults = dict(session=session or current_session(student.school), enrolled_on=date.today(), roll_number=None)
    return Enrollment.objects.create(school=student.school, student=student, school_class=section.school_class, section=section, **{**defaults, **kw})


def assign_teacher(teacher, section, subject=None, session=None, **kw):
    from apps.academics.models import TeacherAssignment

    return TeacherAssignment.objects.create(
        school=teacher.school, teacher=teacher, section=section, subject=subject, session=session or current_session(teacher.school), **kw
    )


def make_exam(school, **kw):
    from apps.examinations.models import Exam, ExamType, GradingScale

    defaults = dict(
        name=f"Exam {_n()}", session=current_session(school), exam_type=ExamType.objects.filter(school=school).first(),
        grading_scale=GradingScale.objects.filter(school=school).first(), start_date=date.today() + timedelta(days=3),
    )
    return Exam.objects.create(school=school, **{**defaults, **kw})


def make_exam_subject(exam, school_class, subject, total=100, passing=33, **kw):
    from apps.examinations.models import ExamSubject

    return ExamSubject.objects.create(
        school=exam.school, exam=exam, school_class=school_class, subject=subject, total_marks=Decimal(total), passing_marks=Decimal(passing), **kw
    )


def make_report_card(exam, student, enrollment, **kw):
    from apps.examinations.models import ReportCard

    defaults = dict(
        total_marks=Decimal("100"), obtained_marks=Decimal("80"), percentage=Decimal("80"), grade="A", gpa=Decimal("3.5"),
        result_status="PASS", breakdown={"lines": []}, computed_at=timezone.now(), published_at=timezone.now(), is_published=True,
    )
    return ReportCard.objects.create(school=exam.school, exam=exam, student=student, enrollment=enrollment, **{**defaults, **kw})


def make_invoice(student, enrollment=None, total="1000.00", paid="0.00", **kw):
    from apps.fees.models import StudentInvoice

    total, paid = Decimal(total), Decimal(paid)
    defaults = dict(
        invoice_number=f"INV-{_n()}", session=current_session(student.school), period_label=f"P{_n()}", issue_date=date.today(),
        due_date=date.today() + timedelta(days=10), subtotal=total, total=total, paid_total=paid, balance=total - paid,
        status="ISSUED" if paid == 0 else "PARTIALLY_PAID",
    )
    return StudentInvoice.objects.create(school=student.school, student=student, enrollment=enrollment, **{**defaults, **kw})


def make_fee_payment(invoice, amount="100.00", **kw):
    from apps.fees.models import FeePayment

    defaults = dict(receipt_number=f"RCT-{_n()}", amount=Decimal(amount), method="CASH", paid_on=date.today())
    return FeePayment.objects.create(school=invoice.school, invoice=invoice, **{**defaults, **kw})


def make_announcement(school, **kw):
    from apps.notifications.models import Announcement

    defaults = dict(title=f"Notice {_n()}", body="Body", audience="ALL", published_at=timezone.now() - timedelta(minutes=1))
    return Announcement.objects.create(school=school, **{**defaults, **kw})
