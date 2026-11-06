from django.test import TestCase

from apps.accounts.roles import Role
from apps.core import factories as f
from apps.core.testing import make_school, png_data_url, staff_client
from apps.tenants.images import ImageService

U = "/api/v1/school"


class IDCardTests(TestCase):
    def setUp(self):
        self.a, self.b = make_school("Alpha"), make_school("Beta")
        _, self.admin = staff_client(self.a, Role.SCHOOL_ADMIN)
        self.section = f.make_section(f.make_class(self.a))
        self.student = f.make_student(self.a)
        self.student.photo = ImageService.store(self.a, png_data_url())
        self.student.save()
        f.enroll(self.student, self.section)

    def pdf(self, response):
        self.assertEqual(response.status_code, 200, getattr(response, "content", b"")[:200])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_single_card_and_section_sheet(self):
        self.pdf(self.admin.get(f"{U}/students/{self.student.id}/id-card/pdf/"))
        for _ in range(11):
            f.enroll(f.make_student(self.a), self.section)
        self.pdf(self.admin.get(f"{U}/reports/id-cards/pdf/?section={self.section.id}"))  # 12 cards = 2 A4 pages

    def test_validation(self):
        unenrolled = f.make_student(self.a)
        self.assertEqual(self.admin.get(f"{U}/students/{unenrolled.id}/id-card/pdf/").status_code, 400)
        self.assertEqual(self.admin.get(f"{U}/reports/id-cards/pdf/").status_code, 400)
        self.assertEqual(self.admin.get(f"{U}/reports/id-cards/pdf/?section=bad").status_code, 400)

    def test_other_schools_students_and_sections_are_not_reachable(self):
        foreign_section = f.make_section(f.make_class(self.b))
        stranger = f.make_student(self.b)
        f.enroll(stranger, foreign_section)
        self.assertEqual(self.admin.get(f"{U}/students/{stranger.id}/id-card/pdf/").status_code, 404)
        self.assertEqual(self.admin.get(f"{U}/reports/id-cards/pdf/?section={foreign_section.id}").status_code, 400)  # no students visible

    def test_permissions(self):
        parent, parent_client = staff_client(self.a, Role.PARENT)
        f.link_guardian(self.student, f.make_guardian(self.a, user=parent))
        self.pdf(parent_client.get(f"{U}/students/{self.student.id}/id-card/pdf/"))  # own child
        self.assertEqual(parent_client.get(f"{U}/reports/id-cards/pdf/?section={self.section.id}").status_code, 403)
        other_child = f.make_student(self.a)
        f.enroll(other_child, self.section)
        self.assertEqual(parent_client.get(f"{U}/students/{other_child.id}/id-card/pdf/").status_code, 404)
        _, teacher = staff_client(self.a, Role.TEACHER)
        self.assertEqual(teacher.get(f"{U}/reports/id-cards/pdf/?section={self.section.id}").status_code, 403)
