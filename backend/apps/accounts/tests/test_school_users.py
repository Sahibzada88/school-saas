from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.testing import TEST_PASSWORD, api_client, login_client, make_school, make_user

URL = "/api/v1/school/users/"
NEW_USER = {
    "email": "new.teacher@school.test",
    "first_name": "Sana",
    "last_name": "Ali",
    "role": Role.TEACHER,
    "password": "Temp-Strong-Pass#42",
}


class SchoolUserApiTests(TestCase):
    def setUp(self):
        self.school_a = make_school("School A")
        self.school_b = make_school("School B")
        self.admin_a = make_user(self.school_a, Role.SCHOOL_ADMIN, email="admin-a@a.test")
        self.teacher_a = make_user(self.school_a, Role.TEACHER, email="teacher-a@a.test")
        self.admin_b = make_user(self.school_b, Role.SCHOOL_ADMIN, email="admin-b@b.test")
        self.teacher_b = make_user(self.school_b, Role.TEACHER, email="teacher-b@b.test")
        self.client_a = login_client(self.admin_a)

    # ------------------------------------------------------------------ authn / authz
    def test_unauthenticated_is_401(self):
        self.assertEqual(api_client().get(URL).status_code, 401)

    def test_non_admin_roles_are_forbidden(self):
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.RECEPTIONIST, Role.PARENT, Role.STUDENT):
            user = make_user(self.school_a, role)
            response = login_client(user).get(URL)
            self.assertEqual(response.status_code, 403, role)
            self.assertEqual(login_client(user).post(URL, NEW_USER).status_code, 403, role)

    def test_super_admin_has_no_tenant_context_on_school_endpoints(self):
        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        response = login_client(root).get(URL)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "tenant_required")

    # ------------------------------------------------------------------ tenant isolation
    def test_list_only_returns_own_school_users(self):
        response = self.client_a.get(URL)
        self.assertEqual(response.status_code, 200)
        emails = {u["email"] for u in response.json()["data"]["results"]}
        self.assertEqual(emails, {"admin-a@a.test", "teacher-a@a.test"})

    def test_school_filter_param_cannot_widen_the_scope(self):
        for param in (f"?school={self.school_b.id}", f"?school_id={self.school_b.id}", f"?school__id={self.school_b.id}"):
            emails = {u["email"] for u in self.client_a.get(URL + param).json()["data"]["results"]}
            self.assertNotIn("teacher-b@b.test", emails, param)

    def test_other_schools_user_is_404_for_read_and_write(self):
        detail = f"{URL}{self.teacher_b.id}/"
        self.assertEqual(self.client_a.get(detail).status_code, 404)
        self.assertEqual(self.client_a.patch(detail, {"first_name": "Hacked"}).status_code, 404)
        self.assertEqual(self.client_a.patch(detail, {"is_active": False}).status_code, 404)
        self.teacher_b.refresh_from_db()
        self.assertNotEqual(self.teacher_b.first_name, "Hacked")
        self.assertTrue(self.teacher_b.is_active)

    def test_own_user_detail_works(self):
        response = self.client_a.get(f"{URL}{self.teacher_a.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["email"], "teacher-a@a.test")
        self.assertNotIn("password", response.json()["data"])

    def test_malformed_ids_are_404_not_500(self):
        self.assertEqual(self.client_a.get(URL + "not-a-uuid/").status_code, 404)

    # ------------------------------------------------------------------ create
    def test_create_assigns_the_actors_school_and_ignores_payload_school(self):
        response = self.client_a.post(URL, {**NEW_USER, "school": str(self.school_b.id), "school_id": str(self.school_b.id)})
        self.assertEqual(response.status_code, 201, response.content)
        created = User.objects.get(email=NEW_USER["email"])
        self.assertEqual(created.school_id, self.school_a.id)
        self.assertTrue(created.must_change_password)
        self.assertNotIn("password", response.json()["data"])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.USER_CREATED, actor=self.admin_a).exists())

    def test_created_user_can_sign_in_but_must_change_password(self):
        self.client_a.post(URL, NEW_USER)
        client = api_client()
        response = client.post("/api/v1/auth/login/", {"email": NEW_USER["email"], "password": NEW_USER["password"]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["user"]["must_change_password"])

    def test_super_admin_role_cannot_be_assigned(self):
        response = self.client_a.post(URL, {**NEW_USER, "role": Role.SUPER_ADMIN})
        self.assertEqual(response.status_code, 400)
        self.assertIn("role", response.json()["errors"])

    def test_email_must_be_unique_globally_and_case_insensitively(self):
        for email in ("teacher-b@b.test", "TEACHER-A@a.test"):
            response = self.client_a.post(URL, {**NEW_USER, "email": email})
            self.assertEqual(response.status_code, 400, email)
            self.assertIn("email", response.json()["errors"])

    def test_weak_password_is_rejected(self):
        response = self.client_a.post(URL, {**NEW_USER, "password": "12345678"})
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------ update
    def test_admin_can_update_a_user(self):
        response = self.client_a.patch(f"{URL}{self.teacher_a.id}/", {"first_name": "Renamed", "role": Role.ACCOUNTANT})
        self.assertEqual(response.status_code, 200)
        self.teacher_a.refresh_from_db()
        self.assertEqual((self.teacher_a.first_name, self.teacher_a.role), ("Renamed", Role.ACCOUNTANT))

    def test_privilege_fields_not_in_the_serializer_are_ignored(self):
        self.client_a.patch(f"{URL}{self.teacher_a.id}/", {"first_name": "X", "school": str(self.school_b.id), "must_change_password": True, "email": "x@x.test"})
        self.teacher_a.refresh_from_db()
        self.assertEqual(self.teacher_a.school_id, self.school_a.id)
        self.assertEqual(self.teacher_a.email, "teacher-a@a.test")
        self.assertFalse(self.teacher_a.must_change_password)

    def test_empty_patch_is_rejected(self):
        self.assertEqual(self.client_a.patch(f"{URL}{self.teacher_a.id}/", {}).status_code, 400)

    def test_admin_cannot_demote_or_deactivate_self(self):
        detail = f"{URL}{self.admin_a.id}/"
        for payload in ({"role": Role.TEACHER}, {"is_active": False}):
            response = self.client_a.patch(detail, payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.json()["code"], "cannot_modify_self")
        self.admin_a.refresh_from_db()
        self.assertEqual(self.admin_a.role, Role.SCHOOL_ADMIN)
        self.assertTrue(self.admin_a.is_active)

    def test_deactivation_signs_the_user_out_and_blocks_login(self):
        teacher_client = login_client(self.teacher_a)
        self.assertEqual(teacher_client.get("/api/v1/auth/me/").status_code, 200)
        response = self.client_a.patch(f"{URL}{self.teacher_a.id}/", {"is_active": False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(teacher_client.get("/api/v1/auth/me/").status_code, 401)
        login = api_client().post("/api/v1/auth/login/", {"email": "teacher-a@a.test", "password": TEST_PASSWORD})
        self.assertEqual(login.status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.USER_DEACTIVATED, actor=self.admin_a).exists())

    def test_put_and_delete_are_not_allowed(self):
        detail = f"{URL}{self.teacher_a.id}/"
        self.assertIn(self.client_a.put(detail, {"first_name": "X"}).status_code, (403, 405))
        self.assertIn(self.client_a.delete(detail).status_code, (403, 405))
        self.assertTrue(User.objects.filter(pk=self.teacher_a.pk).exists())

    # ------------------------------------------------------------------ filters
    def test_search_role_and_active_filters(self):
        self.assertEqual(len(self.client_a.get(URL + "?role=TEACHER").json()["data"]["results"]), 1)
        self.assertEqual(len(self.client_a.get(URL + "?search=teacher-a").json()["data"]["results"]), 1)
        self.assertEqual(len(self.client_a.get(URL + "?is_active=false").json()["data"]["results"]), 0)

    def test_pagination_shape(self):
        data = self.client_a.get(URL + "?page_size=1").json()["data"]
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["pagination"]["total"], 2)
        self.assertEqual(data["pagination"]["total_pages"], 2)
