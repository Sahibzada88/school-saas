import re

from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import AuthSession, LoginAttempt, PasswordResetToken
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.testing import TEST_PASSWORD, api_client, login_client, make_school, make_user

NEW_PASSWORD = "An0ther-Strong-Pass!9"


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.admin = make_user(make_school(), Role.SCHOOL_ADMIN, email="admin@school.test")

    def test_requires_authentication(self):
        response = api_client().post(
            "/api/v1/auth/change-password/", {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_current_password_is_rejected(self):
        client = login_client(self.admin)
        response = client.post("/api/v1/auth/change-password/", {"current_password": "wrong-wrong-1", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json()["errors"])

    def test_weak_new_password_is_rejected(self):
        client = login_client(self.admin)
        response = client.post("/api/v1/auth/change-password/", {"current_password": TEST_PASSWORD, "new_password": "short"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json()["errors"])

    def test_success_rotates_credentials_and_revokes_other_sessions(self):
        client = login_client(self.admin)
        other_device = login_client(self.admin)
        response = client.post("/api/v1/auth/change-password/", {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)  # current device keeps working
        self.assertEqual(other_device.get("/api/v1/auth/me/").status_code, 401)
        self.assertEqual(
            api_client().post("/api/v1/auth/login/", {"email": "admin@school.test", "password": TEST_PASSWORD}).status_code, 401
        )
        self.assertEqual(
            api_client().post("/api/v1/auth/login/", {"email": "admin@school.test", "password": NEW_PASSWORD}).status_code, 200
        )
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PASSWORD_CHANGED, actor=self.admin).exists())


@override_settings(FRONTEND_ORIGIN="http://localhost:3000")
class PasswordResetTests(TestCase):
    def setUp(self):
        self.admin = make_user(make_school(), Role.SCHOOL_ADMIN, email="admin@school.test")

    def request_reset(self, email="admin@school.test", client=None):
        return (client or api_client()).post("/api/v1/auth/password-reset/request/", {"email": email})

    def token_from_mail(self):
        match = re.search(r"/reset-password\?token=([\w-]+)", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_known_and_unknown_emails_get_the_same_response(self):
        known = self.request_reset()
        unknown = self.request_reset("nobody@school.test")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json()["message"], unknown.json()["message"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@school.test"])

    def test_token_is_stored_hashed(self):
        self.request_reset()
        token = self.token_from_mail()
        record = PasswordResetToken.objects.get()
        self.assertNotEqual(record.token_hash, token)
        self.assertEqual(len(record.token_hash), 64)

    def test_full_reset_flow_and_single_use(self):
        old_session_client = login_client(self.admin)
        self.request_reset()
        token = self.token_from_mail()

        response = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": token, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(old_session_client.get("/api/v1/auth/me/").status_code, 401)  # sessions revoked
        self.assertEqual(
            api_client().post("/api/v1/auth/login/", {"email": "admin@school.test", "password": NEW_PASSWORD}).status_code, 200
        )

        reuse = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": token, "new_password": "Yet-An0ther-Pass#7"})
        self.assertEqual(reuse.status_code, 400)
        self.assertIn("token", reuse.json()["errors"])

    def test_invalid_token_is_rejected(self):
        response = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": "not-a-real-token", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)

    def test_weak_password_keeps_the_token_usable(self):
        self.request_reset()
        token = self.token_from_mail()
        weak = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": token, "new_password": "password"})
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.json()["errors"])
        ok = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": token, "new_password": NEW_PASSWORD})
        self.assertEqual(ok.status_code, 200)

    def test_new_request_invalidates_the_previous_token(self):
        self.request_reset()
        first = self.token_from_mail()
        self.request_reset()
        response = api_client().post("/api/v1/auth/password-reset/confirm/", {"token": first, "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)

    def test_per_email_limit_silently_stops_sending(self):
        client = api_client()
        statuses = [self.request_reset(client=client).status_code for _ in range(4)]
        self.assertEqual(statuses, [200, 200, 200, 200])
        self.assertEqual(len(mail.outbox), 3)

    def test_inactive_user_gets_no_email(self):
        type(self.admin).objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
