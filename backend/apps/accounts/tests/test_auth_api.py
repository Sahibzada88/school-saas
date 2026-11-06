from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuthSession, LoginAttempt, User
from apps.accounts.roles import ROLE_PERMISSIONS, Role
from apps.accounts.services.tokens import decode_token
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.csrf import generate_csrf_token
from apps.core.testing import TEST_PASSWORD, api_client, login_client, make_school, make_user
from apps.tenants.models import School, SchoolSettings, SchoolStatus

REGISTER_PAYLOAD = {
    "school_name": "Riverside Academy",
    "admin_name": "Ayesha Khan",
    "email": "Ayesha@Riverside.test",
    "phone": "+92 300 1234567",
    "password": TEST_PASSWORD,
    "country": "Pakistan",
    "city": "Islamabad",
}


class RegistrationTests(TestCase):
    def test_register_creates_school_admin_settings_and_logs_in(self):
        client = api_client()
        response = client.post("/api/v1/auth/register/", REGISTER_PAYLOAD)
        self.assertEqual(response.status_code, 201, response.content)

        user = User.objects.get(email="ayesha@riverside.test")  # normalised to lowercase
        self.assertEqual(user.role, Role.SCHOOL_ADMIN)
        self.assertEqual((user.first_name, user.last_name), ("Ayesha", "Khan"))
        self.assertEqual(user.school.name, "Riverside Academy")
        self.assertEqual(user.school.status, SchoolStatus.ACTIVE)
        self.assertTrue(SchoolSettings.objects.filter(school=user.school).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.SCHOOL_REGISTERED, school=user.school).exists())

        for name in ("access_token", "refresh_token", "sid_hint", "csrf_token"):
            self.assertIn(name, response.cookies)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])
        self.assertEqual(response.cookies["refresh_token"]["path"], "/api/v1/auth/")
        self.assertFalse(response.cookies["csrf_token"]["httponly"])
        self.assertNotIn(TEST_PASSWORD, response.content.decode())

        me = client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        data = me.json()["data"]
        self.assertEqual(data["user"]["role"], Role.SCHOOL_ADMIN)
        self.assertEqual(data["school"]["name"], "Riverside Academy")
        self.assertEqual(data["permissions"], sorted(ROLE_PERMISSIONS[Role.SCHOOL_ADMIN]))

    def test_duplicate_email_is_a_field_error_and_creates_nothing(self):
        make_user(make_school("Other"), email="ayesha@riverside.test")
        before = School.objects.count()
        response = api_client().post("/api/v1/auth/register/", REGISTER_PAYLOAD)
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        self.assertEqual(School.objects.count(), before)

    def test_weak_password_is_rejected(self):
        response = api_client().post("/api/v1/auth/register/", {**REGISTER_PAYLOAD, "password": "12345678"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json()["errors"])

    def test_school_id_and_role_in_payload_are_ignored(self):
        other = make_school("Victim School")
        payload = {**REGISTER_PAYLOAD, "school": str(other.id), "school_id": str(other.id), "role": "SUPER_ADMIN"}
        response = api_client().post("/api/v1/auth/register/", payload)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="ayesha@riverside.test")
        self.assertNotEqual(user.school_id, other.id)
        self.assertEqual(user.role, Role.SCHOOL_ADMIN)

    def test_registration_is_rate_limited_per_ip(self):
        client = api_client()
        statuses = []
        for i in range(7):
            statuses.append(
                client.post("/api/v1/auth/register/", {**REGISTER_PAYLOAD, "email": f"a{i}@riverside.test", "school_name": f"S{i}"}).status_code
            )
        self.assertEqual(statuses[:5], [201] * 5)
        self.assertEqual(statuses[5:], [429, 429])


class LoginTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@school.test")

    def login(self, client=None, email="admin@school.test", password=TEST_PASSWORD):
        return (client or api_client()).post("/api/v1/auth/login/", {"email": email, "password": password})

    def test_login_success_sets_cookies_and_audit(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)
        self.assertEqual(response.json()["data"]["user"]["email"], "admin@school.test")
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.LOGIN, actor=self.admin).exists())
        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.last_login)

    def test_email_is_case_insensitive(self):
        self.assertEqual(self.login(email="ADMIN@School.test").status_code, 200)

    def test_wrong_password_and_unknown_email_look_identical(self):
        wrong = self.login(password="nope-nope-nope")
        unknown = self.login(email="nobody@school.test")
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong.json()["message"], unknown.json()["message"])
        self.assertEqual(wrong.json()["code"], "invalid_credentials")
        self.assertNotIn("access_token", wrong.cookies)

    def test_inactive_user_cannot_login_and_gets_generic_error(self):
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_credentials")

    def test_lockout_after_five_failures_even_with_correct_password(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong-wrong-1").status_code, 401)
        locked = self.login()
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.json()["code"], "too_many_requests")

    def test_success_resets_the_failure_count(self):
        for _ in range(4):
            self.login(password="wrong-wrong-1")
        self.assertEqual(self.login().status_code, 200)
        for _ in range(4):
            self.login(password="wrong-wrong-1")
        self.assertEqual(self.login().status_code, 200)

    def test_failures_of_other_accounts_do_not_lock_this_one(self):
        for _ in range(5):
            self.login(email="someone-else@school.test", password="x" * 12)
        self.assertEqual(self.login().status_code, 200)

    def test_stale_access_cookie_does_not_break_login(self):
        client = api_client()
        client.cookies["access_token"] = "garbage.token.value"
        self.assertEqual(self.login(client).status_code, 200)

    def test_suspended_school_can_sign_in_but_sees_status(self):
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.SUSPENDED, status_reason="Unpaid")
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["school"]["status"], SchoolStatus.SUSPENDED)

    def test_super_admin_login_has_no_school(self):
        make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        response = self.login(email="root@platform.test")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["data"]["school"])


class SessionTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@school.test")

    def test_me_requires_authentication(self):
        response = api_client().get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "not_authenticated")

    def test_tampered_access_cookie_is_rejected(self):
        client = login_client(self.admin)
        client.cookies["access_token"] = client.cookies["access_token"].value[:-4] + "xxxx"
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "token_expired")

    def test_logout_revokes_session_immediately(self):
        client = login_client(self.admin)
        stolen_access = client.cookies["access_token"].value
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)

        response = client.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 401)

        replay = api_client()
        replay.cookies["access_token"] = stolen_access  # a copied token must be dead too
        self.assertEqual(replay.get("/api/v1/auth/me/").status_code, 401)
        self.assertEqual(AuthSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 0)

    def test_deactivating_a_user_kills_existing_sessions(self):
        client = login_client(self.admin)
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 401)

    def test_refresh_rotates_tokens(self):
        client = login_client(self.admin)
        old_refresh = client.cookies["refresh_token"].value
        response = client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.cookies["refresh_token"].value, old_refresh)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)
        old_jti = decode_token(old_refresh, "refresh")["jti"]
        self.assertIsNotNone(AuthSession.objects.get(refresh_jti=old_jti).rotated_at)

    def test_refresh_without_cookie_fails_and_clears_cookies(self):
        response = api_client().post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "session_expired")
        self.assertEqual(response.cookies["access_token"].value, "")

    def test_immediate_replay_is_tolerated_as_a_concurrent_refresh(self):
        client = login_client(self.admin)
        old_refresh = client.cookies["refresh_token"].value
        client.post("/api/v1/auth/refresh/")
        client.cookies["refresh_token"] = old_refresh
        response = client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "token_rotated")
        self.assertNotIn("access_token", response.cookies)  # fresh cookies from the first refresh are kept
        self.assertEqual(AuthSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 2)

    def test_reuse_of_a_rotated_refresh_token_revokes_the_whole_family(self):
        client = login_client(self.admin)
        old_refresh = client.cookies["refresh_token"].value
        client.post("/api/v1/auth/refresh/")
        old_jti = decode_token(old_refresh, "refresh")["jti"]
        AuthSession.objects.filter(refresh_jti=old_jti).update(rotated_at=timezone.now() - timedelta(minutes=5))

        client.cookies["refresh_token"] = old_refresh  # attacker replays the stolen token
        response = client.post("/api/v1/auth/refresh/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "session_expired")
        self.assertEqual(AuthSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 0)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.TOKEN_REUSE_DETECTED, actor=self.admin).exists())

    def test_access_token_cannot_be_used_as_refresh_token(self):
        client = login_client(self.admin)
        client.cookies["refresh_token"] = client.cookies["access_token"].value
        self.assertEqual(client.post("/api/v1/auth/refresh/").status_code, 401)


class CsrfProtectionTests(TestCase):
    def setUp(self):
        self.school = make_school()
        make_user(self.school, Role.SCHOOL_ADMIN, email="admin@school.test")
        self.credentials = {"email": "admin@school.test", "password": TEST_PASSWORD}

    def test_unsafe_request_without_token_is_rejected(self):
        response = APIClient().post("/api/v1/auth/login/", self.credentials)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "csrf_failed")

    def test_header_without_matching_cookie_is_rejected(self):
        client = APIClient()
        client.defaults["HTTP_X_CSRF_TOKEN"] = generate_csrf_token()
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials).status_code, 403)

    def test_mismatched_cookie_and_header_is_rejected(self):
        client = api_client()
        client.defaults["HTTP_X_CSRF_TOKEN"] = generate_csrf_token()
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials).status_code, 403)

    def test_unsigned_matching_token_is_rejected(self):
        client = APIClient()
        client.cookies["csrf_token"] = "attacker.chosen"
        client.defaults["HTTP_X_CSRF_TOKEN"] = "attacker.chosen"
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials).status_code, 403)

    @override_settings(CSRF_TRUSTED_ORIGINS=["http://localhost:3000"], FRONTEND_ORIGIN="")
    def test_untrusted_origin_is_rejected_and_trusted_origin_allowed(self):
        client = api_client()
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials, HTTP_ORIGIN="https://evil.test").status_code, 403)
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials, HTTP_ORIGIN="http://localhost:3000").status_code, 200)

    def test_csrf_endpoint_issues_a_valid_cookie_and_token(self):
        client = APIClient()
        response = client.get("/api/v1/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        token = response.json()["data"]["csrf_token"]
        self.assertEqual(response.cookies["csrf_token"].value, token)
        client.defaults["HTTP_X_CSRF_TOKEN"] = token
        self.assertEqual(client.post("/api/v1/auth/login/", self.credentials).status_code, 200)

    def test_safe_methods_do_not_need_a_token(self):
        self.assertEqual(APIClient().get("/api/v1/health/").status_code, 200)


class AccessGateTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@school.test")

    def test_suspended_school_is_blocked_from_tenant_endpoints_but_not_from_me(self):
        client = login_client(self.admin)
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.SUSPENDED)
        blocked = client.get("/api/v1/school/users/")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "school_disabled")
        self.assertIn("temporarily disabled", blocked.json()["message"])
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)

    def test_inactive_school_is_blocked_and_reactivation_restores_access(self):
        client = login_client(self.admin)
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.INACTIVE)
        self.assertEqual(client.get("/api/v1/school/users/").status_code, 403)
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.ACTIVE)
        self.assertEqual(client.get("/api/v1/school/users/").status_code, 200)

    def test_must_change_password_blocks_tenant_endpoints_until_changed(self):
        User.objects.filter(pk=self.admin.pk).update(must_change_password=True)
        client = login_client(self.admin)
        blocked = client.get("/api/v1/school/users/")
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json()["code"], "password_change_required")

        response = client.post(
            "/api/v1/auth/change-password/",
            {"current_password": TEST_PASSWORD, "new_password": "An0ther-Strong-Pass!9"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["data"]["user"]["must_change_password"])
        self.assertEqual(client.get("/api/v1/school/users/").status_code, 200)
