from django.test import TestCase

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.audit_logs.services import AuditService
from apps.core.testing import api_client, login_client, make_school, make_user
from apps.tenants.models import School, SchoolStatus

PROFILE = "/api/v1/school/profile/"
DASHBOARD = "/api/v1/school/dashboard/"
AUDIT = "/api/v1/school/audit-logs/"


class SchoolProfileTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha Academy")
        self.other = make_school("Beta School")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.client = login_client(self.admin)

    def test_only_the_school_admin_may_read_or_write(self):
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.RECEPTIONIST, Role.PARENT, Role.STUDENT):
            client = login_client(make_user(self.school, role))
            self.assertEqual(client.get(PROFILE).status_code, 403, role)
            self.assertEqual(client.patch(PROFILE, {"city": "X-ville"}).status_code, 403, role)
        root = login_client(make_user(role=Role.SUPER_ADMIN, email="root@platform.test"))
        self.assertEqual(root.get(PROFILE).json()["code"], "tenant_required")
        self.assertEqual(api_client().get(PROFILE).status_code, 401)

    def test_get_returns_own_school_only(self):
        data = self.client.get(PROFILE).json()["data"]
        self.assertEqual(data["id"], str(self.school.id))
        self.assertEqual(data["name"], "Alpha Academy")

    def test_patch_updates_allowed_fields_and_audits_the_changed_ones(self):
        response = self.client.patch(PROFILE, {"city": "Rawalpindi", "phone": "+92 51 1234567", "address": "Main Road"})
        self.assertEqual(response.status_code, 200, response.content)
        self.school.refresh_from_db()
        self.assertEqual((self.school.city, self.school.address), ("Rawalpindi", "Main Road"))
        entry = AuditLog.objects.get(action=AuditAction.SCHOOL_PROFILE_UPDATED)
        self.assertEqual(entry.metadata["fields"], ["address", "city", "phone"])
        self.assertEqual(entry.actor_id, self.admin.id)

    def test_protected_fields_in_the_payload_are_ignored(self):
        original = (self.school.slug, self.school.currency)
        self.client.patch(PROFILE, {"name": "Renamed Academy", "slug": "hijack", "status": "SUSPENDED", "currency": "USD", "id": str(self.other.id)})
        self.school.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.school.name, "Renamed Academy")
        self.assertEqual((self.school.slug, self.school.currency), original)
        self.assertEqual(self.school.status, SchoolStatus.ACTIVE)
        self.assertEqual(self.other.name, "Beta School")

    def test_validation(self):
        self.assertEqual(self.client.patch(PROFILE, {"timezone": "Mars/Olympus"}).status_code, 400)
        self.assertEqual(self.client.patch(PROFILE, {"phone": "call me"}).status_code, 400)
        self.assertEqual(self.client.patch(PROFILE, {"email": "not-an-email"}).status_code, 400)
        self.assertEqual(self.client.patch(PROFILE, {"name": " a "}).status_code, 400)
        self.assertEqual(self.client.patch(PROFILE, {}).status_code, 400)
        self.assertEqual(self.client.patch(PROFILE, {"timezone": "Asia/Karachi"}).status_code, 200)

    def test_unchanged_values_do_not_create_audit_noise(self):
        self.client.patch(PROFILE, {"name": "Alpha Academy"})
        self.assertFalse(AuditLog.objects.filter(action=AuditAction.SCHOOL_PROFILE_UPDATED).exists())

    def test_suspended_school_cannot_edit_its_profile(self):
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.SUSPENDED)
        response = self.client.patch(PROFILE, {"city": "Nowhere"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "school_disabled")


class SchoolDashboardTests(TestCase):
    def setUp(self):
        self.school, self.other = make_school("Alpha"), make_school("Beta")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.client = login_client(self.admin)

    def data(self):
        response = self.client.get(DASHBOARD)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]

    def test_only_the_school_admin_can_view(self):
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.PARENT):
            self.assertEqual(login_client(make_user(self.school, role)).get(DASHBOARD).status_code, 403, role)
        root = login_client(make_user(role=Role.SUPER_ADMIN, email="root@platform.test"))
        self.assertEqual(root.get(DASHBOARD).status_code, 403)

    def test_counts_are_scoped_to_the_school(self):
        make_user(self.school, Role.TEACHER)
        make_user(self.school, Role.TEACHER, is_active=False)
        for _ in range(4):  # another school's users must never be counted
            make_user(self.other, Role.TEACHER)
        users = self.data()["users"]
        self.assertEqual(users["total"], 3)
        self.assertEqual(users["active"], 2)
        self.assertEqual(users["by_role"]["TEACHER"], 2)
        self.assertEqual(users["by_role"]["SCHOOL_ADMIN"], 1)

    def test_checklist_reflects_real_state(self):
        items = {i["key"]: i["done"] for i in self.data()["checklist"]}
        self.assertEqual((items["profile"], items["team"]), (False, False))
        self.client.patch(PROFILE, {"phone": "+92 300 1234567", "address": "Main Road"})
        make_user(self.school, Role.TEACHER)
        items = {i["key"]: i["done"] for i in self.data()["checklist"]}
        self.assertEqual((items["profile"], items["team"]), (True, True))

    def test_recent_activity_is_own_school_only_and_hides_internal_fields(self):
        AuditService.record(AuditAction.USER_UPDATED, school=self.other, description="beta secret")
        activity = self.data()["recent_activity"]
        self.assertTrue(activity)
        self.assertNotIn("beta secret", str(activity))
        for row in activity:
            self.assertNotIn("ip", row)
            self.assertNotIn("metadata", row)


class SchoolAuditLogTests(TestCase):
    def setUp(self):
        self.school, self.other = make_school("Alpha"), make_school("Beta")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.client = login_client(self.admin)

    def test_lists_only_own_school_and_supports_filters(self):
        AuditService.record(AuditAction.USER_CREATED, school=self.school, actor=self.admin, description="created Sana")
        AuditService.record(AuditAction.USER_CREATED, school=self.other, description="created Omar")
        rows = self.client.get(AUDIT).json()["data"]["results"]
        self.assertNotIn("Omar", str(rows))
        self.assertEqual(len(self.client.get(f"{AUDIT}?action={AuditAction.USER_CREATED}").json()["data"]["results"]), 1)
        self.assertEqual(len(self.client.get(f"{AUDIT}?search=Sana").json()["data"]["results"]), 1)

    def test_platform_staff_are_shown_generically_and_without_ip(self):
        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        AuditService.record(AuditAction.SCHOOL_SUSPENDED, school=self.school, actor=root, description="School suspended: Review")
        row = next(r for r in self.client.get(AUDIT).json()["data"]["results"] if r["action"] == AuditAction.SCHOOL_SUSPENDED)
        self.assertEqual(row["actor_name"], "Platform administration")
        self.assertNotIn("root@platform.test", str(row))
        self.assertNotIn("ip", row)

    def test_other_roles_are_forbidden(self):
        self.assertEqual(login_client(make_user(self.school, Role.TEACHER)).get(AUDIT).status_code, 403)

    def test_entries_are_read_only(self):
        entry = AuditService.record(AuditAction.LOGIN, school=self.school)
        detail = f"{AUDIT}{entry.id}/"
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertIn(self.client.delete(detail).status_code, (403, 405))
        self.assertIn(self.client.patch(detail, {"description": "x"}).status_code, (403, 405))
        self.assertIn(self.client.post(AUDIT, {"action": "X"}).status_code, (403, 405))
