from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.core.testing import login_client, make_school, make_user
from apps.platform_admin.models import PlatformSetting
from apps.subscriptions.models import Subscription, SubscriptionStatus as S

DAY = timedelta(days=1)
USERS = "/api/v1/school/users/"
PROFILE = "/api/v1/school/profile/"
NEW_USER = {"email": "new@school.test", "first_name": "New", "role": "TEACHER", "password": "Temp-Strong-Pass#42"}


class SubscriptionAccessTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@school.test")
        self.client = login_client(self.admin)
        self.now = timezone.now()

    def set_sub(self, **fields):
        if "trial_end" in fields and "trial_start" not in fields:
            fields["trial_start"] = fields["trial_end"] - 30 * DAY
        Subscription.objects.filter(school=self.school).update(**fields)

    def expire_trial(self):
        self.set_sub(status=S.TRIALING, trial_end=self.now - DAY)

    def test_trial_has_full_access(self):
        self.assertEqual(self.client.get(USERS).status_code, 200)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 201)

    def test_expired_is_read_only_viewing_works_writing_gets_402(self):
        self.expire_trial()
        self.assertEqual(self.client.get(USERS).status_code, 200)
        self.assertEqual(self.client.get(PROFILE).status_code, 200)
        for response in (self.client.post(USERS, NEW_USER), self.client.patch(PROFILE, {"city": "Elsewhere"})):
            self.assertEqual(response.status_code, 402)
            self.assertEqual(response.json()["code"], "subscription_expired")
        self.assertFalse(type(self.admin).objects.filter(email="new@school.test").exists())

    def test_expired_school_can_still_use_account_and_notification_endpoints(self):
        self.expire_trial()
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["subscription"]["state"], S.EXPIRED)
        self.assertEqual(me.json()["data"]["subscription"]["access"], "READ_ONLY")
        self.assertEqual(self.client.get("/api/v1/notifications/").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/notifications/mark-all-read/").status_code, 200)
        change = self.client.post("/api/v1/auth/change-password/", {"current_password": "Str0ng-Test-Pass#2026", "new_password": "An0ther-Strong-Pass!9"})
        self.assertEqual(change.status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout/").status_code, 200)

    def test_blocked_mode_locks_expired_schools_out_of_tenant_endpoints_entirely(self):
        PlatformSetting.objects.create(key="expired_access_mode", value="BLOCKED")
        self.expire_trial()
        response = self.client.get(USERS)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "subscription_blocked")
        me = self.client.get("/api/v1/auth/me/")  # but the app can still explain why
        self.assertEqual(me.json()["data"]["subscription"]["access"], "BLOCKED")

    def test_suspended_subscription_is_blocked(self):
        self.set_sub(status=S.SUSPENDED)
        self.assertEqual(self.client.get(USERS).json()["code"], "subscription_blocked")
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 403)

    def test_grace_period_keeps_full_access(self):
        self.set_sub(status=S.ACTIVE, start_date=self.now - 40 * DAY, end_date=self.now - 2 * DAY)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 201)
        me = self.client.get("/api/v1/auth/me/").json()["data"]["subscription"]
        self.assertEqual((me["state"], me["access"], me["in_grace"]), (S.PAST_DUE, "FULL", True))

    def test_after_the_grace_period_writes_stop(self):
        self.set_sub(status=S.ACTIVE, start_date=self.now - 60 * DAY, end_date=self.now - 20 * DAY)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 402)

    def test_grace_length_is_a_platform_setting(self):
        PlatformSetting.objects.create(key="past_due_grace_days", value=30)
        self.set_sub(status=S.ACTIVE, start_date=self.now - 60 * DAY, end_date=self.now - 20 * DAY)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 201)

    def test_cancelled_subscription_works_until_the_paid_period_ends(self):
        self.set_sub(status=S.CANCELLED, start_date=self.now - 20 * DAY, end_date=self.now + 5 * DAY)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 201)

    def test_access_returns_as_soon_as_the_subscription_is_extended(self):
        self.expire_trial()
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 402)
        self.set_sub(status=S.ACTIVE, start_date=self.now, end_date=self.now + 30 * DAY)
        self.assertEqual(self.client.post(USERS, NEW_USER).status_code, 201)

    def test_school_suspension_still_takes_precedence(self):
        from apps.tenants.models import School, SchoolStatus

        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.SUSPENDED)
        self.assertEqual(self.client.get(USERS).json()["code"], "school_disabled")

    def test_me_exposes_a_school_safe_subscription_summary(self):
        data = self.client.get("/api/v1/auth/me/").json()["data"]["subscription"]
        self.assertEqual((data["state"], data["access"], data["is_trial"]), (S.TRIALING, "FULL", True))
        self.assertEqual(set(data), {"state", "access", "days_remaining", "is_expiring", "in_grace", "ends_at", "is_trial", "plan"})

    def test_super_admin_me_has_no_subscription(self):
        root = login_client(make_user(role=Role.SUPER_ADMIN, email="root@platform.test"))
        self.assertIsNone(root.get("/api/v1/auth/me/").json()["data"]["subscription"])
