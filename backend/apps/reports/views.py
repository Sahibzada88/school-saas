from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework.exceptions import NotFound, ValidationError

import base64

from apps.academics.models import Enrollment, EnrollmentStatus
from apps.accounts.roles import P
from apps.attendance.services import StudentAttendanceService
from apps.attendance.views import scoped_attendance
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import ExportTooLarge
from apps.core.responses import success_response
from apps.core.viewsets import TenantAPIView
from apps.examinations.models import Exam
from apps.examinations.views import scoped_report_cards
from apps.fees.models import FeePayment, StudentInvoice
from apps.students.models import Student
from apps.students.scope import visible_students
from apps.teachers.models import Teacher

from . import builders
from .csv_service import MAX_CSV_ROWS, CSVExportService, safe_filename
from .pdf_service import MAX_PDF_ROWS, PDFService


def _audit_export(request, dataset: str, rows: int, fmt: str) -> None:
    AuditService.record(
        AuditAction.EXPORT_GENERATED, actor=request.user, school=request.user.school, entity_type="export", entity_id=dataset,
        description=f"Exported {dataset} ({fmt}, {rows} row(s))", metadata={"dataset": dataset, "rows": rows, "format": fmt}, request=request,
    )


def pdf_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{safe_filename(filename)}.pdf"'
    response["Cache-Control"] = "no-store"
    return response


# ===================================================================== CSV exports
class _CSVExport(TenantAPIView):
    dataset = ""

    def build(self, request):  # -> (header, rows_iterable, count)
        raise NotImplementedError

    def get(self, request):
        header, rows, count = self.build(request)
        if count > MAX_CSV_ROWS:
            raise ExportTooLarge()
        _audit_export(request, self.dataset, count, "csv")
        return CSVExportService.respond(f"{self.dataset}-{date.today().isoformat()}", header, rows, count=count)


class StudentsCSVView(_CSVExport):
    required_permission = P.EXPORT_STUDENTS
    dataset = "students"

    def build(self, request):
        queryset = builders.students_queryset(request.user, request.query_params)
        header = ["student_number", "first_name", "last_name", "gender", "date_of_birth", "status", "class", "section", "roll_number", "phone", "email", "guardian", "guardian_phone"]
        rows = (
            [s.student_number, s.first_name, s.last_name, s.gender, s.date_of_birth, s.status, s.class_name, s.section_name, s.roll, s.phone, s.email, s.guardian_name, s.guardian_phone]
            for s in queryset.iterator(chunk_size=2000)
        )
        return header, rows, queryset.count()


class TeachersCSVView(_CSVExport):
    required_permission = P.EXPORT_TEACHERS
    dataset = "teachers"

    def build(self, request):
        queryset = Teacher.objects.filter(school=request.user.school).order_by("first_name", "last_name")
        header = ["employee_id", "first_name", "last_name", "gender", "phone", "email", "qualification", "joining_date", "status"]
        rows = ([t.employee_id, t.first_name, t.last_name, t.gender, t.phone, t.email, t.qualification, t.joining_date, t.status] for t in queryset.iterator(chunk_size=2000))
        return header, rows, queryset.count()


class AttendanceCSVView(_CSVExport):
    required_permission = P.EXPORT_ATTENDANCE
    dataset = "attendance"

    def build(self, request):
        queryset = scoped_attendance(request.user)
        params = request.query_params
        if params.get("section"):
            queryset = queryset.filter(section_id=params["section"])
        if params.get("date_from"):
            queryset = queryset.filter(date__gte=params["date_from"])
        if params.get("date_to"):
            queryset = queryset.filter(date__lte=params["date_to"])
        queryset = queryset.order_by("date", "section__school_class__level_order", "student__first_name")
        header = ["date", "student_number", "student", "class", "section", "status", "remarks"]
        rows = ([a.date, a.student.student_number, a.student.full_name, a.section.school_class.name, a.section.name, a.status, a.remarks] for a in queryset.iterator(chunk_size=2000))
        return header, rows, queryset.count()


class FeesCSVView(_CSVExport):
    required_permission = P.EXPORT_FEES
    dataset = "fees"

    def build(self, request):
        queryset = StudentInvoice.objects.filter(school=request.user.school).select_related("student").order_by("-issue_date", "invoice_number")
        params = request.query_params
        if params.get("status"):
            queryset = queryset.filter(status=params["status"])
        if params.get("session"):
            queryset = queryset.filter(session_id=params["session"])
        header = ["invoice_number", "student_number", "student", "period", "issue_date", "due_date", "total", "paid", "balance", "status"]
        rows = ([i.invoice_number, i.student.student_number, i.student.full_name, i.period_label, i.issue_date, i.due_date, i.total, i.paid_total, i.balance, i.status] for i in queryset.iterator(chunk_size=2000))
        return header, rows, queryset.count()


class ResultsCSVView(_CSVExport):
    required_permission = P.EXPORT_EXAMS
    dataset = "results"

    def build(self, request):
        exam_id = request.query_params.get("exam")
        if not exam_id:
            raise ValidationError({"exam": ["Choose an exam to export."]})
        try:
            queryset = scoped_report_cards(request.user).filter(exam_id=exam_id).order_by("enrollment__school_class__level_order", "enrollment__section__name", "position_section")
            count = queryset.count()
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"exam": ["Invalid exam."]}) from exc
        header = ["student_number", "student", "class", "section", "total_marks", "obtained_marks", "percentage", "grade", "gpa", "position_section", "position_class", "result"]
        rows = (
            [c.student.student_number, c.student.full_name, c.enrollment.school_class.name, c.enrollment.section.name, c.total_marks, c.obtained_marks, c.percentage, c.grade, c.gpa, c.position_section, c.position_class, c.result_status]
            for c in queryset.iterator(chunk_size=2000)
        )
        return header, rows, count


# ===================================================================== PDF documents
class ResultPDFView(TenantAPIView):
    required_permission = P.RESULTS_VIEW

    def get(self, request, card_id):
        card = scoped_report_cards(request.user).filter(pk=card_id).first()
        if card is None:
            raise NotFound()
        _audit_export(request, "report-card", 1, "pdf")
        return pdf_response(PDFService.generate_result_pdf(card), f"report-card-{card.student.student_number}-{card.exam.name}")


class TranscriptPDFView(TenantAPIView):
    required_permission = P.RESULTS_VIEW

    def get(self, request, student_id):
        cards = list(scoped_report_cards(request.user).filter(student_id=student_id).order_by("exam__session__start_date", "exam__start_date"))
        if not cards:
            raise NotFound()
        student = cards[0].student
        _audit_export(request, "transcript", len(cards), "pdf")
        return pdf_response(PDFService.generate_transcript_pdf(student, cards[0].school.name, cards), f"transcript-{student.student_number}")


class ReceiptPDFView(TenantAPIView):
    required_permission = P.FEES_VIEW

    def get(self, request, payment_id):
        students = visible_students(request.user, Student.objects.filter(school=request.user.school))
        payment = FeePayment.objects.select_related("invoice__student", "invoice__school").filter(school=request.user.school, pk=payment_id, invoice__student__in=students).first()
        if payment is None:
            raise NotFound()
        _audit_export(request, "fee-receipt", 1, "pdf")
        return pdf_response(PDFService.generate_fee_receipt_pdf(payment), f"receipt-{payment.receipt_number}")


class InvoicePDFView(TenantAPIView):
    required_permission = P.FEES_VIEW

    def get(self, request, invoice_id):
        students = visible_students(request.user, Student.objects.filter(school=request.user.school))
        invoice = StudentInvoice.objects.select_related("student", "school").prefetch_related("items", "discounts", "fines", "payments").filter(school=request.user.school, pk=invoice_id, student__in=students).first()
        if invoice is None:
            raise NotFound()
        _audit_export(request, "fee-invoice", 1, "pdf")
        return pdf_response(PDFService.generate_invoice_pdf(invoice), f"invoice-{invoice.invoice_number}")


class CertificatePDFView(TenantAPIView):
    required_permission = P.STUDENTS_LIFECYCLE

    def get(self, request, student_id):
        student = Student.objects.filter(school=request.user.school, pk=student_id).first()
        if student is None:
            raise NotFound()
        enrollment = Enrollment.objects.select_related("school_class", "section", "session").filter(student=student).order_by("-session__start_date").first()
        if enrollment is None:
            raise ValidationError({"detail": ["This student has no enrollment yet."]})
        _audit_export(request, "certificate", 1, "pdf")
        label = f"Class {enrollment.school_class.name} (Section {enrollment.section.name})"
        return pdf_response(PDFService.generate_certificate_pdf(student, request.user.school.name, label, enrollment.session.name), f"certificate-{student.student_number}")


class AttendanceReportPDFView(TenantAPIView):
    required_permission = P.REPORTS_VIEW

    def get(self, request):
        section_id = request.query_params.get("section")
        if not section_id:
            raise ValidationError({"section": ["Choose a section."]})
        queryset = scoped_attendance(request.user).filter(section_id=section_id)
        month = request.query_params.get("month") or date.today().strftime("%Y-%m")
        report = StudentAttendanceService.monthly(queryset=queryset, month=month)
        if len(report["students"]) > MAX_PDF_ROWS:
            raise ExportTooLarge()
        first = queryset.first()
        label = f"{first.section.school_class.name}-{first.section.name}" if first else "Section"
        _audit_export(request, "attendance-report", len(report["students"]), "pdf")
        return pdf_response(PDFService.generate_attendance_report_pdf(request.user.school.name, label, report), f"attendance-{label}-{month}")


class OutstandingFeesPDFView(TenantAPIView):
    required_permission = P.FEES_MANAGE

    def get(self, request):
        data = builders.outstanding(request.user.school, request.query_params, limit=MAX_PDF_ROWS + 1)
        if len(data["rows"]) > MAX_PDF_ROWS:
            raise ExportTooLarge()
        _audit_export(request, "outstanding-fees", len(data["rows"]), "pdf")
        return pdf_response(PDFService.generate_outstanding_fees_pdf(request.user.school.name, data["rows"], data["total"]), "outstanding-fees")


class StudentListPDFView(TenantAPIView):
    required_permission = P.STUDENTS_VIEW

    def get(self, request):
        queryset = builders.students_queryset(request.user, request.query_params)
        rows = [[s.student_number, s.full_name, s.gender, f"{s.class_name or '-'}-{s.section_name or '-'}", s.status, s.phone] for s in queryset[: MAX_PDF_ROWS + 1]]
        if len(rows) > MAX_PDF_ROWS:
            raise ExportTooLarge()
        _audit_export(request, "student-list", len(rows), "pdf")
        return pdf_response(PDFService.generate_student_list_pdf(request.user.school.name, rows), "student-list")


def _card_for(enrollment, school_name: str) -> dict:
    student = enrollment.student
    photo = None
    if student.photo_id:
        try:
            photo = base64.b64decode(student.photo.data_base64)
        except Exception:
            photo = None
    return {
        "school": school_name, "name": student.full_name, "number": student.student_number,
        "class_label": f"{enrollment.school_class.name}-{enrollment.section.name}", "session": enrollment.session.name, "photo": photo,
    }


class StudentIDCardPDFView(TenantAPIView):
    required_permission = P.STUDENTS_VIEW

    def get(self, request, student_id):
        students = visible_students(request.user, Student.objects.filter(school=request.user.school))
        student = students.filter(pk=student_id).select_related("photo").first()
        if student is None:
            raise NotFound()
        enrollment = Enrollment.objects.select_related("school_class", "section", "session", "student__photo").filter(student=student, session__is_current=True).first()
        if enrollment is None:
            raise ValidationError({"detail": ["The student is not enrolled in the current session, so there is no class to print."]})
        _audit_export(request, "id-card", 1, "pdf")
        return pdf_response(PDFService.generate_id_cards_pdf([_card_for(enrollment, request.user.school.name)], sheet=False), f"id-card-{student.student_number}")


class SectionIDCardsPDFView(TenantAPIView):
    """A4 sheet of ID cards for one section (admin/receptionist)."""

    required_permission = P.STUDENTS_MANAGE

    def get(self, request):
        section_id = request.query_params.get("section")
        if not section_id:
            raise ValidationError({"section": ["Choose a section."]})
        try:
            enrollments = list(
                Enrollment.objects.filter(school=request.user.school, section_id=section_id, session__is_current=True, status=EnrollmentStatus.ENROLLED)
                .select_related("school_class", "section", "session", "student__photo").order_by("roll_number", "student__first_name")[: MAX_PDF_ROWS + 1]
            )
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"section": ["Invalid section."]}) from exc
        if len(enrollments) > MAX_PDF_ROWS:
            raise ExportTooLarge()
        if not enrollments:
            raise ValidationError({"detail": ["There are no enrolled students in this section."]})
        _audit_export(request, "id-cards", len(enrollments), "pdf")
        return pdf_response(PDFService.generate_id_cards_pdf([_card_for(e, request.user.school.name) for e in enrollments], sheet=True), "id-cards")


# ===================================================================== JSON reports (the UI renders these; PDF/CSV are separate downloads)
class OutstandingFeesReportView(TenantAPIView):
    required_permission = P.FEES_MANAGE

    def get(self, request):
        return success_response(builders.outstanding(request.user.school, request.query_params, limit=500), message="")


class StudentsSummaryReportView(TenantAPIView):
    required_permission = P.STUDENTS_VIEW

    def get(self, request):
        return success_response(builders.students_summary(request.user), message="")


class ExamAnalysisReportView(TenantAPIView):
    required_permission = P.RESULTS_PUBLISH

    def get(self, request, exam_id):
        exam = Exam.objects.filter(school=request.user.school, pk=exam_id).first()
        if exam is None:
            raise NotFound()
        return success_response(builders.exam_analysis(exam), message="")
