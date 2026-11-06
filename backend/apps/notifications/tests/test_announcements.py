from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client

URL = "/api/v1/school/announcements/"


class AnnouncementFixture(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin_user, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.class_x, self.class_y = f.make_class(self.school), f.make_class(self.school)
        self.section_x = f.make_section(self.class_x)
        for audience, cls in (("ALL", None), ("STAFF", None), ("TEACHERS", None), ("PARENTS", None), ("STUDENTS", None), ("CLASS", self.class_x), ("CLASS", self.class_y)):
            f.make_announcement(self.school, title=f"{audience}{'-X' if cls == self.class_x else '-Y' if cls == self.class_y else ''}", audience=audience, school_class=cls)

    def titles(self, client):
        return {a["title"] for a in client.get(URL + "?page_size=100").json()["data"]["results"]}


class VisibilityTests(AnnouncementFixture):
    def test_admin_sees_everything(self):
        self.assertEqual(len(self.titles(self.admin)), 7)

    def test_staff_roles(self):
        for role in (Role.ACCOUNTANT, Role.RECEPTIONIST):
            _, client = staff_client(self.school, role)
            self.assertEqual(self.titles(client), {"ALL", "STAFF"}, role)

    def test_teacher_gets_class_posts_only_for_classes_they_teach(self):
        user, client = staff_client(self.school, Role.TEACHER)
        profile = f.make_teacher(self.school, user=user)
        self.assertEqual(self.titles(client), {"ALL", "STAFF", "TEACHERS"})
        f.assign_teacher(profile, self.section_x)
        self.assertEqual(self.titles(client), {"ALL", "STAFF", "TEACHERS", "CLASS-X"})

    def test_parent_and_student_audiences(self):
        parent, parent_client = staff_client(self.school, Role.PARENT)
        child = f.make_student(self.school)
        f.link_guardian(child, f.make_guardian(self.school, user=parent))
        self.assertEqual(self.titles(parent_client), {"ALL", "PARENTS"})
        f.enroll(child, self.section_x)
        self.assertEqual(self.titles(parent_client), {"ALL", "PARENTS", "CLASS-X"})
        student_user, student_client = staff_client(self.school, Role.STUDENT)
        self.assertEqual(self.titles(student_client), {"ALL", "STUDENTS"})
        type(child).objects.filter(pk=child.pk).update(user=student_user)
        self.assertEqual(self.titles(student_client), {"ALL", "STUDENTS", "CLASS-X"})

    def test_expired_and_future_posts_are_hidden_from_non_admins(self):
        f.make_announcement(self.school, title="Old", expires_at=timezone.now() - timedelta(days=1))
        f.make_announcement(self.school, title="Soon", published_at=timezone.now() + timedelta(days=1))
        _, client = staff_client(self.school, Role.ACCOUNTANT)
        self.assertNotIn("Old", self.titles(client))
        self.assertNotIn("Soon", self.titles(client))
        self.assertTrue({"Old", "Soon"} <= self.titles(self.admin))

    def test_pinned_posts_come_first(self):
        f.make_announcement(self.school, title="Pinned", is_pinned=True)
        first = self.admin.get(URL).json()["data"]["results"][0]
        self.assertEqual(first["title"], "Pinned")


class PostingTests(AnnouncementFixture):
    def body(self, **kw):
        return {"title": "Sports day", "body": "On Friday", "audience": "ALL", **kw}

    def test_admin_posts_and_it_is_audited(self):
        response = self.admin.post(URL, self.body(is_pinned=True))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["data"]["created_by_name"], self.admin_user.full_name)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.ANNOUNCEMENT_CREATED).exists())

    def test_class_audience_needs_a_class_and_other_audiences_drop_it(self):
        self.assertEqual(self.admin.post(URL, self.body(audience="CLASS")).status_code, 400)
        response = self.admin.post(URL, self.body(audience="STAFF", school_class=str(self.class_x.id)))
        self.assertIsNone(response.json()["data"]["school_class"])
        foreign = f.make_class(make_school("Beta"))
        self.assertEqual(self.admin.post(URL, self.body(audience="CLASS", school_class=str(foreign.id))).status_code, 400)

    def test_teacher_can_post_only_to_their_own_classes(self):
        user, teacher = staff_client(self.school, Role.TEACHER)
        f.assign_teacher(f.make_teacher(self.school, user=user), self.section_x)
        self.assertEqual(teacher.post(URL, self.body(audience="CLASS", school_class=str(self.class_x.id))).status_code, 201)
        self.assertEqual(teacher.post(URL, self.body(audience="CLASS", school_class=str(self.class_y.id))).status_code, 403)
        self.assertEqual(teacher.post(URL, self.body(audience="ALL")).status_code, 403)

    def test_teacher_can_edit_only_their_own_posts(self):
        user, teacher = staff_client(self.school, Role.TEACHER)
        f.assign_teacher(f.make_teacher(self.school, user=user), self.section_x)
        mine = teacher.post(URL, self.body(audience="CLASS", school_class=str(self.class_x.id))).json()["data"]["id"]
        self.assertEqual(teacher.patch(f"{URL}{mine}/", {"title": "Edited"}).status_code, 200)
        admins_post = self.admin.post(URL, self.body(audience="CLASS", school_class=str(self.class_x.id))).json()["data"]["id"]
        self.assertEqual(teacher.patch(f"{URL}{admins_post}/", {"title": "Hijack"}).status_code, 403)
        self.assertEqual(teacher.delete(f"{URL}{admins_post}/").status_code, 403)

    def test_other_roles_cannot_post(self):
        for role in (Role.PARENT, Role.STUDENT, Role.ACCOUNTANT, Role.RECEPTIONIST):
            _, client = staff_client(self.school, role)
            self.assertEqual(client.post(URL, self.body()).status_code, 403, role)

    def test_expiry_must_follow_publishing(self):
        now = timezone.now()
        response = self.admin.post(URL, self.body(published_at=now.isoformat(), expires_at=(now - timedelta(hours=1)).isoformat()))
        self.assertEqual(response.status_code, 400)

    def test_delete_is_soft(self):
        announcement = f.make_announcement(self.school, title="Temp")
        self.assertEqual(self.admin.delete(f"{URL}{announcement.id}/").status_code, 204)
        self.assertEqual(self.admin.get(f"{URL}{announcement.id}/").status_code, 404)
        self.assertTrue(type(announcement).all_objects.filter(pk=announcement.pk, is_deleted=True).exists())


class ReadReceiptTests(AnnouncementFixture):
    def test_read_marks_and_unread_count(self):
        _, client = staff_client(self.school, Role.ACCOUNTANT)
        self.assertEqual(client.get(URL + "unread-count/").json()["data"]["count"], 2)
        first = client.get(URL).json()["data"]["results"][0]
        self.assertFalse(first["is_read"])
        self.assertEqual(client.post(f"{URL}{first['id']}/read/").status_code, 200)
        self.assertEqual(client.post(f"{URL}{first['id']}/read/").status_code, 200)  # idempotent
        self.assertEqual(client.get(URL + "unread-count/").json()["data"]["count"], 1)
        mine = {a["id"]: a["is_read"] for a in client.get(URL).json()["data"]["results"]}
        self.assertTrue(mine[first["id"]])

    def test_read_state_is_per_user(self):
        _, one = staff_client(self.school, Role.ACCOUNTANT)
        _, two = staff_client(self.school, Role.RECEPTIONIST)
        one.post(f"{URL}{one.get(URL).json()['data']['results'][0]['id']}/read/")
        self.assertEqual(two.get(URL + "unread-count/").json()["data"]["count"], 2)

    def test_cannot_mark_an_invisible_announcement_as_read(self):
        _, client = staff_client(self.school, Role.ACCOUNTANT)
        hidden = type(f.make_announcement(self.school)).objects.get(title="TEACHERS")
        self.assertEqual(client.post(f"{URL}{hidden.id}/read/").status_code, 404)
