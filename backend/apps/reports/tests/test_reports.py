from datetime import date
from unittest import mock

from django.test import TestCase

from apps.accounts.roles import Role
from apps.attendance.models import StudentAttendance
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client

U = "/api/v1/school"


def body(response) -> str:
    return b"".join(response.streaming_content).decode("utf-8-sig")


class TwoSchools(TestCase):
    """School A and School B each own students, invoices, results, attendance. Nothing of B may reach A's exports."""

    def setUp(self):
        self.a, self.b = make_school("Alpha"), make_school("Beta")
        self.admin_user, self.admin = staff_client(self.a, Role.SCHOOL_ADMIN)
        self.data = {}
        for key, school, first in (("a", self.a, "Anna"), ("b", self.b, "Bobby")):
            section = f.make_section(f.make_class(school))
            student = f.make_student(school, first_name=first, last_name="Student")
            enrollment = f.enroll(student, section)
            exam = f.make_exam(school, name=f"Exam {first}")
            card = f.make_report_card(exam, student, enrollment)
            invoice = f.make_invoice(student, enrollment)
            payment = f.make_fee_payment(invoice)
            StudentAttendance.objects.create(school=school, student=student, enrollment=enrollment, section=section, date=date.today(), status="PRESENT")
            self.data[key] = dict(section=section, student=student, enrollment=enrollment, exam=exam, card=card, invoice=invoice, payment=payment)


class CSVExportTests(TwoSchools):
    def test_students_csv_contains_only_own_school_rows(self):
        text = body(self.admin.get(f"{U}/exports/students/csv/"))
        self.assertIn("Anna", text)
        self.assertNotIn("Bobby", text)
        self.assertTrue(text.startswith("student_number,first_name"))

    def test_every_export_is_tenant_scoped(self):
        urls = {
            "teachers": f"{U}/exports/teachers/csv/", "attendance": f"{U}/exports/attendance/csv/", "fees": f"{U}/exports/fees/csv/",
            "results": f"{U}/exports/results/csv/?exam={self.data['a']['exam'].id}",
        }
        f.make_teacher(self.a, first_name="Tara")
        f.make_teacher(self.b, first_name="Tessa")
        for name, url in urls.items():
            response = self.admin.get(url)
            self.assertEqual(response.status_code, 200, (name, response.content))
            text = body(response)
            self.assertNotIn("Bobby", text, name)
            self.assertNotIn(self.data["b"]["invoice"].invoice_number, text, name)
            self.assertNotIn("Tessa", text, name)
        self.assertIn(self.data["a"]["invoice"].invoice_number, body(self.admin.get(urls["fees"])))
        self.assertIn("Tara", body(self.admin.get(urls["teachers"])))

    def test_results_export_for_another_schools_exam_is_empty_not_leaked(self):
        text = body(self.admin.get(f"{U}/exports/results/csv/?exam={self.data['b']['exam'].id}"))
        self.assertEqual(len(text.strip().splitlines()), 1)  # header only
        self.assertEqual(self.admin.get(f"{U}/exports/results/csv/").status_code, 400)
        self.assertEqual(self.admin.get(f"{U}/exports/results/csv/?exam=nope").status_code, 400)

    def test_formula_injection_is_neutralised(self):
        f.make_student(self.a, first_name="=HYPERLINK(\"http://evil\")", last_name="@SUM(A1)")
        text = body(self.admin.get(f"{U}/exports/students/csv/"))
        self.assertIn("'=HYPERLINK", text)
        self.assertIn("'@SUM(A1)", text)
        self.assertNotIn(",=HYPERLINK", text)

    def test_headers_filename_and_audit_log(self):
        response = self.admin.get(f"{U}/exports/students/csv/")
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment; filename=\"students-", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store")
        entry = AuditLog.objects.get(action=AuditAction.EXPORT_GENERATED)
        self.assertEqual((entry.school_id, entry.metadata["dataset"], entry.metadata["format"]), (self.a.id, "students", "csv"))

    def test_permissions(self):
        for role, url, allowed in (
            (Role.RECEPTIONIST, "students", True), (Role.TEACHER, "students", False), (Role.PARENT, "students", False), (Role.STUDENT, "fees", False),
            (Role.ACCOUNTANT, "fees", True), (Role.ACCOUNTANT, "students", False), (Role.TEACHER, "attendance", True), (Role.TEACHER, "teachers", False),
        ):
            _, client = staff_client(self.a, role)
            self.assertEqual(client.get(f"{U}/exports/{url}/csv/").status_code == 200, allowed, (role, url))

    def test_teacher_attendance_export_is_limited_to_their_sections(self):
        user, client = staff_client(self.a, Role.TEACHER)
        text = body(client.get(f"{U}/exports/attendance/csv/"))
        self.assertEqual(len(text.strip().splitlines()), 1)  # not assigned anywhere yet: header only
        f.assign_teacher(f.make_teacher(self.a, user=user), self.data["a"]["section"])
        self.assertIn("Anna", body(client.get(f"{U}/exports/attendance/csv/")))

    def test_oversized_exports_are_refused_with_413(self):
        with mock.patch("apps.reports.views.MAX_CSV_ROWS", 0):
            response = self.admin.get(f"{U}/exports/students/csv/")
        self.assertEqual((response.status_code, response.json()["code"]), (413, "export_too_large"))


class PDFTests(TwoSchools):
    def assert_pdf(self, response):
        self.assertEqual(response.status_code, 200, getattr(response, "content", b"")[:200])
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("attachment", response["Content-Disposition"])

    def test_documents_for_own_school(self):
        d = self.data["a"]
        self.assert_pdf(self.admin.get(f"{U}/results/{d['card'].id}/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/results/transcript/{d['student'].id}/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/fees/payments/{d['payment'].id}/receipt/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/fees/invoices/{d['invoice'].id}/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/students/{d['student'].id}/certificate/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/reports/attendance/pdf/?section={d['section'].id}"))
        self.assert_pdf(self.admin.get(f"{U}/reports/fees/outstanding/pdf/"))
        self.assert_pdf(self.admin.get(f"{U}/reports/students/pdf/"))

    def test_other_schools_documents_are_404(self):
        d = self.data["b"]
        for url in (f"results/{d['card'].id}/pdf/", f"results/transcript/{d['student'].id}/pdf/", f"fees/payments/{d['payment'].id}/receipt/pdf/",
                    f"fees/invoices/{d['invoice'].id}/pdf/", f"students/{d['student'].id}/certificate/pdf/"):
            self.assertEqual(self.admin.get(f"{U}/{url}").status_code, 404, url)
        self.assertEqual(self.admin.get(f"{U}/reports/attendance/pdf/?section={d['section'].id}").status_code, 200)  # empty report, no foreign rows
        self.assertNotIn(b"Bobby", self.admin.get(f"{U}/reports/students/pdf/").content)

    def test_families_can_download_only_their_own_documents(self):
        parent, client = staff_client(self.a, Role.PARENT)
        mine = self.data["a"]
        f.link_guardian(mine["student"], f.make_guardian(self.a, user=parent))
        self.assert_pdf(client.get(f"{U}/results/{mine['card'].id}/pdf/"))
        self.assert_pdf(client.get(f"{U}/fees/payments/{mine['payment'].id}/receipt/pdf/"))
        sibling = f.make_student(self.a)
        enrollment = f.enroll(sibling, mine["section"])
        other_card = f.make_report_card(mine["exam"], sibling, enrollment)
        self.assertEqual(client.get(f"{U}/results/{other_card.id}/pdf/").status_code, 404)
        self.assertEqual(client.get(f"{U}/students/{mine['student'].id}/certificate/pdf/").status_code, 403)  # admin-only document
        self.assertEqual(client.get(f"{U}/reports/fees/outstanding/pdf/").status_code, 403)

    def test_unpublished_results_have_no_pdf(self):
        card = self.data["a"]["card"]
        type(card).objects.filter(pk=card.pk).update(is_published=False)
        self.assertEqual(self.admin.get(f"{U}/results/{card.id}/pdf/").status_code, 404)

    def test_certificate_needs_an_enrollment(self):
        self.assertEqual(self.admin.get(f"{U}/students/{f.make_student(self.a).id}/certificate/pdf/").status_code, 400)

    def test_pdf_generation_is_audited(self):
        self.admin.get(f"{U}/fees/invoices/{self.data['a']['invoice'].id}/pdf/")
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.EXPORT_GENERATED, metadata__dataset="fee-invoice").exists())


class JsonReportTests(TwoSchools):
    def test_outstanding_fees_report_is_scoped_and_totals_are_right(self):
        f.make_invoice(self.data["a"]["student"], self.data["a"]["enrollment"], total="500.00")
        data = self.admin.get(f"{U}/reports/fees/outstanding/").json()["data"]
        self.assertEqual((data["count"], data["total"]), (2, "1500.00"))
        self.assertEqual({r["student_name"] for r in data["rows"]}, {"Anna Student"})

    def test_students_summary(self):
        data = self.admin.get(f"{U}/reports/students/summary/").json()["data"]
        self.assertEqual((data["total"], data["by_status"], data["by_gender"]), (1, {"ACTIVE": 1}, {"MALE": 1}))

    def test_exam_analysis(self):
        exam = self.data["a"]["exam"]
        subject = f.make_exam_subject(exam, self.data["a"]["enrollment"].school_class, f.make_subject(self.a), total=100, passing=40)
        from apps.examinations.models import Mark

        d = self.data["a"]
        Mark.objects.create(school=self.a, exam_subject=subject, enrollment=d["enrollment"], student=d["student"], obtained_marks=70)
        data = self.admin.get(f"{U}/reports/exams/{exam.id}/").json()["data"]
        self.assertEqual((data["students"], data["passed"], data["pass_rate"]), (1, 1, 100.0))
        self.assertEqual((data["subjects"][0]["average"], data["subjects"][0]["pass_rate"]), ("70.00", 100.0))
        self.assertEqual(self.admin.get(f"{U}/reports/exams/{self.data['b']['exam'].id}/").status_code, 404)

    def test_report_permissions(self):
        for role in (Role.TEACHER, Role.PARENT, Role.STUDENT):
            _, client = staff_client(self.a, role)
            self.assertEqual(client.get(f"{U}/reports/fees/outstanding/").status_code, 403, role)
