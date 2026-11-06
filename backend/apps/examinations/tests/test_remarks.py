from django.test import TestCase

from apps.accounts.roles import Role
from apps.core import factories as f
from apps.core.testing import make_school, staff_client


class RemarksTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin_user, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.section_a = f.make_section(f.make_class(self.school))
        self.section_b = f.make_section(f.make_class(self.school))
        self.exam = f.make_exam(self.school)
        self.cards = {}
        for key, section in (("a", self.section_a), ("b", self.section_b)):
            student = f.make_student(self.school)
            self.cards[key] = f.make_report_card(self.exam, student, f.enroll(student, section))
        self.teacher_user, self.teacher = staff_client(self.school, Role.TEACHER)
        f.assign_teacher(f.make_teacher(self.school, user=self.teacher_user), self.section_a)

    def url(self, key):
        return f"/api/v1/school/results/{self.cards[key].id}/remarks/"

    def test_teacher_writes_remarks_for_their_own_section_only(self):
        ok = self.teacher.post(self.url("a"), {"teacher_remarks": "Hardworking student."})
        self.assertEqual((ok.status_code, ok.json()["data"]["teacher_remarks"]), (200, "Hardworking student."))
        self.assertEqual(self.teacher.post(self.url("b"), {"teacher_remarks": "x"}).status_code, 404)  # not their section

    def test_principal_remarks_are_admin_only(self):
        self.assertEqual(self.teacher.post(self.url("a"), {"principal_remarks": "Promoted."}).status_code, 403)
        both = self.admin.post(self.url("b"), {"teacher_remarks": "Good", "principal_remarks": "Promoted."})
        self.assertEqual((both.status_code, both.json()["data"]["principal_remarks"]), (200, "Promoted."))

    def test_validation_and_other_roles(self):
        self.assertEqual(self.admin.post(self.url("a"), {"teacher_remarks": "x" * 301}).status_code, 400)
        for role in (Role.PARENT, Role.STUDENT, Role.ACCOUNTANT):
            _, client = staff_client(self.school, role)
            self.assertEqual(client.post(self.url("a"), {"teacher_remarks": "x"}).status_code, 403, role)

    def test_remarks_appear_on_the_report_card_pdf(self):
        self.admin.post(self.url("a"), {"teacher_remarks": "Excellent progress"})
        response = self.admin.get(f"/api/v1/school/results/{self.cards['a'].id}/pdf/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
