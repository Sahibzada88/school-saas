"""Query-count guards: list endpoints must not issue more queries as the data grows (N+1 detection)."""
from datetime import date

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.accounts.roles import Role
from apps.attendance.models import StudentAttendance
from apps.core import factories as f
from apps.core.testing import make_school, staff_client

U = "/api/v1/school"


class QueryCountTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.section = f.make_section(f.make_class(self.school))
        self.exam = f.make_exam(self.school)
        self.counter = 0
        self.grow(3)

    def grow(self, n):
        for _ in range(n):
            student = f.make_student(self.school)
            enrollment = f.enroll(student, self.section, roll_number=self.counter + 1)
            self.counter += 1
            f.make_report_card(self.exam, student, enrollment)
            invoice = f.make_invoice(student, enrollment)
            f.make_fee_payment(invoice)
            StudentAttendance.objects.create(school=self.school, student=student, enrollment=enrollment, section=self.section, date=date.today(), status="PRESENT")
            f.link_guardian(student, f.make_guardian(self.school))

    def queries(self, url) -> int:
        self.client.get(url)  # warm-up (session lookups etc.)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx)

    def test_list_endpoints_do_not_grow_with_the_data(self):
        urls = [
            f"{U}/students/", f"{U}/enrollments/", f"{U}/guardians/", f"{U}/sections/", f"{U}/results/", f"{U}/fees/invoices/",
            f"{U}/fees/payments/", f"{U}/attendance/records/", f"{U}/exams/", f"{U}/classes/", f"{U}/audit-logs/",
        ]
        small = {url: self.queries(url) for url in urls}
        self.grow(40)
        for url in urls:
            large = self.queries(url + "?page_size=100")
            self.assertLessEqual(large, small[url] + 1, f"{url}: {small[url]} queries with 3 rows, {large} with 43 rows (N+1?)")
            self.assertLessEqual(large, 14, url)

    def test_detail_and_roster_endpoints_stay_flat(self):
        student = f.make_student(self.school)
        f.enroll(student, self.section)
        roster_url = f"{U}/attendance/roster/?section={self.section.id}"
        before = self.queries(roster_url)
        self.grow(30)
        self.assertLessEqual(self.queries(roster_url), before + 1)
        self.assertLessEqual(self.queries(f"{U}/students/{student.id}/"), 12)
