from django.urls import path

from . import views

urlpatterns = [
    path("exports/students/csv/", views.StudentsCSVView.as_view(), name="export-students"),
    path("exports/teachers/csv/", views.TeachersCSVView.as_view(), name="export-teachers"),
    path("exports/attendance/csv/", views.AttendanceCSVView.as_view(), name="export-attendance"),
    path("exports/fees/csv/", views.FeesCSVView.as_view(), name="export-fees"),
    path("exports/results/csv/", views.ResultsCSVView.as_view(), name="export-results"),
    path("results/<uuid:card_id>/pdf/", views.ResultPDFView.as_view(), name="result-pdf"),
    path("results/transcript/<uuid:student_id>/pdf/", views.TranscriptPDFView.as_view(), name="transcript-pdf"),
    path("fees/payments/<uuid:payment_id>/receipt/pdf/", views.ReceiptPDFView.as_view(), name="receipt-pdf"),
    path("fees/invoices/<uuid:invoice_id>/pdf/", views.InvoicePDFView.as_view(), name="invoice-pdf"),
    path("students/<uuid:student_id>/certificate/pdf/", views.CertificatePDFView.as_view(), name="certificate-pdf"),
    path("students/<uuid:student_id>/id-card/pdf/", views.StudentIDCardPDFView.as_view(), name="id-card-pdf"),
    path("reports/id-cards/pdf/", views.SectionIDCardsPDFView.as_view(), name="id-cards-pdf"),
    path("reports/attendance/pdf/", views.AttendanceReportPDFView.as_view(), name="attendance-report-pdf"),
    path("reports/fees/outstanding/pdf/", views.OutstandingFeesPDFView.as_view(), name="outstanding-fees-pdf"),
    path("reports/students/pdf/", views.StudentListPDFView.as_view(), name="student-list-pdf"),
    path("reports/fees/outstanding/", views.OutstandingFeesReportView.as_view(), name="outstanding-fees-report"),
    path("reports/students/summary/", views.StudentsSummaryReportView.as_view(), name="students-summary-report"),
    path("reports/exams/<uuid:exam_id>/", views.ExamAnalysisReportView.as_view(), name="exam-analysis-report"),
]
