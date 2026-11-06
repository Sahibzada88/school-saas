from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import login_client, make_school, make_user, png_data_url, staff_client
from apps.students.models import Guardian, Student, StudentStatus
from apps.subscriptions.models import Plan

URL = "/api/v1/school/students/"
NEW = {"first_name": "Zain", "last_name": "Ahmed", "date_of_birth": "2012-05-01", "gender": "MALE"}


class AdmissionTests(TestCase):
    def setUp(self):
        self.school, self.other = make_school("Alpha"), make_school("Beta")
        self.admin, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)

    def test_student_numbers_are_sequential_and_per_school(self):
        first = self.client.post(URL, NEW)
        second = self.client.post(URL, {**NEW, "first_name": "Omar"})
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual([first.json()["data"]["student_number"], second.json()["data"]["student_number"]], ["STU-00001", "STU-00002"])
        _, other_client = staff_client(self.other, Role.SCHOOL_ADMIN)
        self.assertEqual(other_client.post(URL, NEW).json()["data"]["student_number"], "STU-00001")  # independent counters

    def test_validation(self):
        for override in ({"date_of_birth": "2999-01-01"}, {"phone": "call me"}, {"gender": "ROBOT"}, {"first_name": ""}, {"email": "nope"}):
            self.assertEqual(self.client.post(URL, {**NEW, **override}).status_code, 400, override)

    def test_school_and_number_in_the_payload_are_ignored(self):
        response = self.client.post(URL, {**NEW, "school": str(self.other.id), "student_number": "HACK-1", "status": "GRADUATED"})
        self.assertEqual(response.status_code, 201)
        student = Student.objects.get(pk=response.json()["data"]["id"])
        self.assertEqual((student.school_id, student.student_number, student.status), (self.school.id, "STU-00001", StudentStatus.ACTIVE))

    def test_linking_a_user_from_another_school_is_rejected(self):
        foreign_user = make_user(self.other, Role.STUDENT)
        response = self.client.post(URL, {**NEW, "user": str(foreign_user.id)})
        self.assertEqual(response.status_code, 400)
        self.assertIn("user", response.json()["errors"])

    def test_plan_limit_is_enforced(self):
        plan = Plan.objects.create(name="Tiny", slug="tiny", monthly_price="1", max_students=1)
        self.school.subscription.plan = plan
        self.school.subscription.save()
        self.assertEqual(self.client.post(URL, NEW).status_code, 201)
        blocked = self.client.post(URL, {**NEW, "first_name": "Second"})
        self.assertEqual((blocked.status_code, blocked.json()["code"]), (403, "plan_limit_reached"))

    def test_roles(self):
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        self.assertEqual(reception.post(URL, NEW).status_code, 201)  # admission is allowed
        student_id = Student.objects.get().id
        self.assertEqual(reception.delete(f"{URL}{student_id}/").status_code, 403)  # lifecycle is not
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.PARENT, Role.STUDENT):
            _, client = staff_client(self.school, role)
            self.assertEqual(client.post(URL, NEW).status_code, 403, role)

    def test_delete_is_soft_and_audited(self):
        student = f.make_student(self.school)
        self.assertEqual(self.client.delete(f"{URL}{student.id}/").status_code, 204)
        self.assertFalse(Student.objects.filter(pk=student.pk).exists())
        self.assertTrue(Student.all_objects.filter(pk=student.pk, is_deleted=True).exists())  # data is kept
        self.assertEqual(self.client.get(f"{URL}{student.id}/").status_code, 404)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.STUDENT_DELETED).exists())

    def test_deleted_numbers_can_be_reused_but_active_ones_stay_unique(self):
        student = f.make_student(self.school, student_number="X-1")
        student.delete()
        self.assertTrue(f.make_student(self.school, student_number="X-1").pk)  # partial unique index ignores deleted rows
        with self.assertRaises(IntegrityError), transaction.atomic():
            f.make_student(self.school, student_number="X-1")

    def test_filters_search_and_bad_filters(self):
        f.make_student(self.school, first_name="Bilal", last_name="Raza")
        f.make_student(self.school, first_name="Hina", last_name="Shah", status="INACTIVE")
        rows = lambda q: self.client.get(f"{URL}?{q}").json()["data"]["results"]
        self.assertEqual(len(rows("search=bilal")), 1)
        self.assertEqual(len(rows("status=INACTIVE")), 1)
        self.assertEqual(self.client.get(f"{URL}?section=not-a-uuid").status_code, 400)

    def test_status_change_ends_the_current_enrollment(self):
        student = f.make_student(self.school)
        enrollment = f.enroll(student, f.make_section(f.make_class(self.school)))
        response = self.client.post(f"{URL}{student.id}/change-status/", {"status": "TRANSFERRED", "reason": "Moved city"})
        self.assertEqual(response.status_code, 200, response.content)
        enrollment.refresh_from_db()
        self.assertEqual((enrollment.status, enrollment.ended_on is not None), ("TRANSFERRED", True))
        self.assertEqual(self.client.post(f"{URL}{student.id}/change-status/", {"status": "TRANSFERRED"}).status_code, 409)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.STUDENT_STATUS_CHANGED).exists())


class PhotoTests(TestCase):
    def setUp(self):
        self.school, self.other = make_school("Alpha"), make_school("Beta")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)

    def test_photo_is_stored_validated_and_served_privately(self):
        response = self.client.post(URL, {**NEW, "photo": png_data_url()})
        self.assertEqual(response.status_code, 201, response.content)
        url = response.json()["data"]["photo_url"]
        self.assertTrue(url.startswith("/api/v1/school/images/"))
        served = self.client.get(url)
        self.assertEqual((served.status_code, served["Content-Type"]), (200, "image/png"))
        self.assertIn("private", served["Cache-Control"])
        self.assertEqual(self.client.get(url, HTTP_IF_NONE_MATCH=served["ETag"]).status_code, 304)
        _, other_client = staff_client(self.other, Role.SCHOOL_ADMIN)
        self.assertEqual(other_client.get(url).status_code, 404)  # another school cannot fetch it

    def test_invalid_photos_are_rejected_without_creating_the_student(self):
        for bad in ("not-an-image", "data:image/svg+xml;base64,PHN2Zy8+", png_data_url(size=(600, 600))):
            self.assertEqual(self.client.post(URL, {**NEW, "photo": bad}).status_code, 400)
        self.assertFalse(Student.objects.exists())

    def test_replacing_and_removing_a_photo_deletes_the_old_one(self):
        from apps.tenants.models import ImageAsset

        student_id = self.client.post(URL, {**NEW, "photo": png_data_url()}).json()["data"]["id"]
        self.client.patch(f"{URL}{student_id}/", {"photo": png_data_url(color="blue")})
        self.assertEqual(ImageAsset.objects.filter(school=self.school).count(), 1)
        self.client.patch(f"{URL}{student_id}/", {"photo": None})
        self.assertEqual(ImageAsset.objects.filter(school=self.school).count(), 0)
        self.assertIsNone(self.client.get(f"{URL}{student_id}/").json()["data"]["photo_url"])


class ScopeTests(TestCase):
    """Who sees which students."""

    def setUp(self):
        self.school = make_school("Alpha")
        self.section_a = f.make_section(f.make_class(self.school))
        self.section_b = f.make_section(f.make_class(self.school))
        self.in_a, self.in_b = f.make_student(self.school, first_name="InA"), f.make_student(self.school, first_name="InB")
        f.enroll(self.in_a, self.section_a)
        f.enroll(self.in_b, self.section_b)

    def names(self, client):
        return {r["first_name"] for r in client.get(URL).json()["data"]["results"]}

    def test_teacher_sees_only_students_of_assigned_sections(self):
        user, client = staff_client(self.school, Role.TEACHER)
        f.assign_teacher(f.make_teacher(self.school, user=user), self.section_a)
        self.assertEqual(self.names(client), {"InA"})
        self.assertEqual(client.get(f"{URL}{self.in_b.id}/").status_code, 404)

    def test_unassigned_teacher_sees_nobody(self):
        _, client = staff_client(self.school, Role.TEACHER)
        self.assertEqual(self.names(client), set())

    def test_parent_sees_only_their_children(self):
        parent, client = staff_client(self.school, Role.PARENT)
        f.link_guardian(self.in_a, f.make_guardian(self.school, user=parent))
        self.assertEqual(self.names(client), {"InA"})
        self.assertEqual(client.get(f"{URL}{self.in_b.id}/").status_code, 404)
        self.assertEqual(client.patch(f"{URL}{self.in_a.id}/", {"first_name": "X"}).status_code, 403)

    def test_student_sees_only_themselves(self):
        user, client = staff_client(self.school, Role.STUDENT)
        Student.objects.filter(pk=self.in_b.pk).update(user=user)
        self.assertEqual(self.names(client), {"InB"})

    def test_admin_receptionist_accountant_see_everyone(self):
        for role in (Role.SCHOOL_ADMIN, Role.RECEPTIONIST, Role.ACCOUNTANT):
            _, client = staff_client(self.school, role)
            self.assertEqual(self.names(client), {"InA", "InB"}, role)


class GuardianTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.student = f.make_student(self.school)
        self.url = f"{URL}{self.student.id}/guardians/"

    def test_link_a_new_guardian_inline_and_an_existing_one(self):
        response = self.client.post(self.url, {"new_guardian": {"first_name": "Ahmed", "last_name": "Khan", "phone": "+92 300 1234567"}, "relationship": "FATHER", "is_primary": True})
        self.assertEqual(response.status_code, 201, response.content)
        mother = f.make_guardian(self.school, first_name="Sara")
        self.assertEqual(self.client.post(self.url, {"guardian": str(mother.id), "relationship": "MOTHER", "is_primary": True}).status_code, 201)
        links = self.client.get(self.url).json()["data"]
        self.assertEqual({(l["guardian"]["first_name"], l["is_primary"]) for l in links}, {("Ahmed", False), ("Sara", True)})  # primary moved

    def test_duplicates_and_bad_payloads_are_rejected(self):
        guardian = f.make_guardian(self.school)
        self.client.post(self.url, {"guardian": str(guardian.id)})
        self.assertEqual(self.client.post(self.url, {"guardian": str(guardian.id)}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"guardian": str(guardian.id), "new_guardian": {"first_name": "A", "phone": "+92 300 1234567"}}).status_code, 400)

    def test_cannot_link_another_schools_guardian(self):
        foreign = f.make_guardian(make_school("Beta"))
        self.assertEqual(self.client.post(self.url, {"guardian": str(foreign.id)}).status_code, 400)

    def test_unlink(self):
        link = f.link_guardian(self.student, f.make_guardian(self.school))
        self.assertEqual(self.client.delete(f"{self.url}{link.id}/").status_code, 200)
        self.assertEqual(self.client.delete(f"{self.url}{link.id}/").status_code, 404)
        self.assertTrue(Guardian.objects.filter(pk=link.guardian_id).exists())  # the guardian record stays

    def test_only_roles_with_guardian_permission_can_link(self):
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.post(self.url, {"new_guardian": {"first_name": "A", "phone": "+92 300 1234567"}}).status_code, 403)
