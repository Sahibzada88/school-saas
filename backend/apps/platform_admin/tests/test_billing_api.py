from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.testing import api_client, login_client, make_school, make_user
from apps.notifications.models import Notification, NotificationType
from apps.payments.models import PlatformPayment
from apps.platform_admin.models import PlatformSetting
from apps.subscriptions.models import Plan, Subscription, SubscriptionStatus as S

BASE = "/api/v1/platform"
DAY = timedelta(days=1)
PLAN = {"name": "Standard", "slug": "standard", "monthly_price": "10000.00", "currency": "pkr", "max_students": 600, "features": ["Exams", "Fees"]}


class BillingAccessTests(TestCase):
    URLS = ["/plans/", "/subscriptions/", "/payments/", "/settings/"]

    def setUp(self):
        self.school = make_school()
        self.sub = self.school.subscription

    def test_anonymous_and_school_users_are_rejected_everywhere(self):
        anon = api_client()
        for url in self.URLS:
            self.assertEqual(anon.get(BASE + url).status_code, 401, url)
        for role in (Role.SCHOOL_ADMIN, Role.ACCOUNTANT):
            client = login_client(make_user(self.school, role))
            for url in self.URLS:
                self.assertEqual(client.get(BASE + url).status_code, 403, (role, url))
            self.assertEqual(client.post(f"{BASE}/plans/", PLAN).status_code, 403)
            self.assertEqual(client.patch(f"{BASE}/settings/", {"trial_duration_days": 30}).status_code, 403)
            self.assertEqual(client.post(f"{BASE}/subscriptions/{self.sub.id}/extend-trial/", {"days": 5, "reason": "free stuff"}).status_code, 403)
        self.assertEqual(Plan.objects.count(), 0)


class PlanApiTests(TestCase):
    def setUp(self):
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)

    def test_create_normalises_and_audits(self):
        response = self.client.post(f"{BASE}/plans/", PLAN)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()["data"]
        self.assertEqual((data["currency"], data["monthly_price"], data["subscriber_count"], data["max_teachers"]), ("PKR", "10000.00", 0, None))
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PLAN_CREATED, actor=self.root).exists())

    def test_validation(self):
        self.client.post(f"{BASE}/plans/", PLAN)
        for override in ({"slug": "standard"}, {"monthly_price": "-1"}, {"currency": "XX"}, {"slug": "Not A Slug!"}, {"max_students": -5}, {"name": ""}, {"features": ["x"] * 21}):
            self.assertEqual(self.client.post(f"{BASE}/plans/", {**PLAN, "slug": "other", **override}).status_code, 400, override)

    def test_update_keeps_the_slug_and_can_retire_a_plan(self):
        plan_id = self.client.post(f"{BASE}/plans/", PLAN).json()["data"]["id"]
        response = self.client.patch(f"{BASE}/plans/{plan_id}/", {"slug": "hijack", "monthly_price": "12000", "is_active": False})
        self.assertEqual(response.status_code, 200, response.content)
        plan = Plan.objects.get(pk=plan_id)
        self.assertEqual((plan.slug, str(plan.monthly_price), plan.is_active), ("standard", "12000.00", False))
        self.assertEqual(self.client.patch(f"{BASE}/plans/{plan_id}/", {}).status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PLAN_UPDATED).exists())

    def test_list_includes_subscriber_counts_and_there_is_no_delete(self):
        plan = Plan.objects.create(name="Basic", slug="basic", monthly_price="5")
        Subscription.objects.filter(school=make_school()).update(plan=plan)
        data = self.client.get(f"{BASE}/plans/").json()["data"]
        self.assertEqual([(p["slug"], p["subscriber_count"]) for p in data], [("basic", 1)])
        self.assertIn(self.client.delete(f"{BASE}/plans/{plan.id}/").status_code, (403, 405))
        self.assertTrue(Plan.objects.filter(pk=plan.pk).exists())

    def test_public_plans_endpoint_hides_inactive_and_private_plans(self):
        Plan.objects.create(name="Basic", slug="basic", monthly_price="5000", sort_order=1)
        Plan.objects.create(name="Retired", slug="retired", monthly_price="1", is_active=False)
        Plan.objects.create(name="Custom", slug="custom", monthly_price="9", is_public=False)
        response = api_client().get("/api/v1/plans/")  # no authentication needed
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual([p["slug"] for p in data], ["basic"])
        self.assertEqual(data[0]["monthly_price"], "5000.00")


class SubscriptionApiTests(TestCase):
    def setUp(self):
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)
        self.now = timezone.now()
        self.alpha, self.beta, self.gamma = make_school("Alpha"), make_school("Beta"), make_school("Gamma")
        self.admin = make_user(self.alpha, Role.SCHOOL_ADMIN)
        Subscription.objects.filter(school=self.beta).update(status=S.TRIALING, trial_start=self.now - 20 * DAY, trial_end=self.now - DAY)
        Subscription.objects.filter(school=self.gamma).update(status=S.ACTIVE, start_date=self.now - 20 * DAY, end_date=self.now + 3 * DAY)
        self.plan = Plan.objects.create(name="Pro", slug="pro", monthly_price="20000")

    def url(self, school, action=""):
        return f"{BASE}/subscriptions/{school.subscription.id}/{action}"

    def rows(self, query=""):
        response = self.client.get(f"{BASE}/subscriptions/?{query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["data"]["results"]

    def test_list_reports_the_effective_state_not_just_the_stored_one(self):
        by_school = {r["school"]["name"]: r for r in self.rows()}
        self.assertEqual(by_school["Beta"]["status"], S.TRIALING)  # nobody has synced it yet...
        self.assertEqual(by_school["Beta"]["state"], S.EXPIRED)  # ...but it is already expired
        self.assertEqual(by_school["Alpha"]["state"], S.TRIALING)
        self.assertEqual((by_school["Gamma"]["state"], by_school["Gamma"]["is_expiring"]), (S.ACTIVE, True))

    def test_filters(self):
        self.assertEqual([r["school"]["name"] for r in self.rows("state=EXPIRED")], ["Beta"])
        self.assertEqual([r["school"]["name"] for r in self.rows("expiring=true")], ["Gamma"])
        self.assertEqual([r["school"]["name"] for r in self.rows("search=alp")], ["Alpha"])
        Subscription.objects.filter(school=self.alpha).update(plan=self.plan)
        self.assertEqual([r["school"]["name"] for r in self.rows("plan=pro")], ["Alpha"])
        self.assertEqual(self.client.get(f"{BASE}/subscriptions/?state=BOGUS").status_code, 400)
        self.assertEqual([r["school"]["name"] for r in self.rows("ordering=school")], ["Alpha", "Beta", "Gamma"])

    def test_school_list_filters_by_subscription_state(self):
        rows = self.client.get(f"{BASE}/schools/?subscription_state=EXPIRED").json()["data"]["results"]
        self.assertEqual([r["name"] for r in rows], ["Beta"])
        self.assertEqual(rows[0]["subscription"]["state"], S.EXPIRED)
        self.assertEqual(self.client.get(f"{BASE}/schools/?subscription_state=BOGUS").status_code, 400)

    def test_extend_trial_via_api(self):
        self.assertEqual(self.client.post(self.url(self.alpha, "extend-trial/"), {"days": 5}).status_code, 400)  # reason required
        self.assertEqual(self.client.post(self.url(self.alpha, "extend-trial/"), {"days": 0, "reason": "valid reason"}).status_code, 400)
        response = self.client.post(self.url(self.beta, "extend-trial/"), {"days": 7, "reason": "Second chance"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["state"], S.TRIALING)
        self.assertEqual(self.client.post(self.url(self.gamma, "extend-trial/"), {"days": 7, "reason": "paid already"}).status_code, 409)

    def test_extend_subscription_and_change_plan(self):
        end = Subscription.objects.get(school=self.gamma).end_date  # fresh read: the cached relation predates setUp's update
        self.assertEqual(self.client.post(self.url(self.gamma, "extend/"), {"days": 10, "reason": "Goodwill"}).status_code, 200)
        self.assertEqual(Subscription.objects.get(school=self.gamma).end_date, end + 10 * DAY)
        self.assertEqual(self.client.post(self.url(self.alpha, "extend/"), {"days": 10, "reason": "never paid"}).status_code, 409)
        self.assertEqual(self.client.post(self.url(self.gamma, "change-plan/"), {"plan": str(self.plan.id)}).status_code, 200)
        self.assertEqual(self.client.post(self.url(self.gamma, "change-plan/"), {"plan": str(self.plan.id)}).status_code, 409)
        self.assertEqual(self.client.post(self.url(self.gamma, "change-plan/"), {"plan": "00000000-0000-0000-0000-000000000000"}).status_code, 400)

    def test_cancel_suspend_resume_need_confirmation_and_follow_the_state_rules(self):
        for action in ("cancel/", "suspend/"):
            self.assertEqual(self.client.post(self.url(self.gamma, action), {"reason": "valid reason"}).status_code, 400, action)  # no confirm
            self.assertEqual(self.client.post(self.url(self.gamma, action), {"confirm": True}).status_code, 400, action)  # no reason
        self.assertEqual(self.client.post(self.url(self.gamma, "cancel/"), {"reason": "School closing", "confirm": True}).json()["data"]["state"], S.CANCELLED)
        self.assertEqual(self.client.post(self.url(self.gamma, "cancel/"), {"reason": "again please", "confirm": True}).status_code, 409)
        self.assertEqual(self.client.post(self.url(self.alpha, "suspend/"), {"reason": "Chargeback", "confirm": True}).json()["data"]["state"], S.SUSPENDED)
        self.assertEqual(self.client.post(self.url(self.alpha, "resume/"), {}).json()["data"]["state"], S.TRIALING)
        self.assertEqual(self.client.post(self.url(self.alpha, "resume/"), {}).status_code, 409)

    def test_events_history_and_audit_trail(self):
        self.client.post(self.url(self.alpha, "extend-trial/"), {"days": 3, "reason": "Help with setup"})
        events = self.client.get(self.url(self.alpha, "events/")).json()["data"]
        self.assertEqual([e["event_type"] for e in events], ["TRIAL_EXTENDED", "TRIAL_STARTED"])
        self.assertEqual(events[0]["actor_name"], self.root.full_name)
        self.assertEqual(events[0]["delta_days"], 3)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.SUBSCRIPTION_TRIAL_EXTENDED, school=self.alpha).exists())

    def test_other_http_methods_are_not_available(self):
        for method in ("delete", "put", "patch"):
            self.assertIn(getattr(self.client, method)(self.url(self.alpha), {}).status_code, (403, 405))
        self.assertIn(self.client.get(self.url(self.alpha, "cancel/")).status_code, (403, 405))


class SettingsApiTests(TestCase):
    def setUp(self):
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)

    def test_get_describes_every_setting_with_its_default(self):
        data = {s["key"]: s for s in self.client.get(f"{BASE}/settings/").json()["data"]}
        self.assertEqual(data["trial_duration_days"]["value"], 7)
        self.assertEqual(data["past_due_grace_days"]["value"], 5)
        self.assertEqual(data["expired_access_mode"]["choices"], ["READ_ONLY", "BLOCKED"])
        self.assertEqual(data["trial_duration_days"]["minimum"], 1)

    def test_patch_updates_validates_and_audits(self):
        response = self.client.patch(f"{BASE}/settings/", {"trial_duration_days": 14, "expired_access_mode": "BLOCKED"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual({s["key"]: s["value"] for s in response.json()["data"]}["trial_duration_days"], 14)
        self.assertEqual(PlatformSetting.objects.get(key="trial_duration_days").updated_by_id, self.root.id)
        entry = AuditLog.objects.get(action=AuditAction.PLATFORM_SETTING_CHANGED)
        self.assertEqual(entry.metadata["changes"]["trial_duration_days"], {"from": 7, "to": 14})

    def test_invalid_values_are_rejected_per_key_and_nothing_is_saved(self):
        response = self.client.patch(f"{BASE}/settings/", {"trial_duration_days": 0, "expired_access_mode": "NEVER", "bogus": 1, "past_due_grace_days": "5"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"trial_duration_days", "expired_access_mode", "bogus", "past_due_grace_days"})
        self.assertFalse(PlatformSetting.objects.exists())
        self.assertEqual(self.client.patch(f"{BASE}/settings/", {"trial_duration_days": True}).status_code, 400)  # bool is not a number
        self.assertEqual(self.client.patch(f"{BASE}/settings/", {}).status_code, 400)

    def test_unchanged_values_do_not_write_or_audit(self):
        self.client.patch(f"{BASE}/settings/", {"trial_duration_days": 7})
        self.assertFalse(PlatformSetting.objects.exists())
        self.assertFalse(AuditLog.objects.filter(action=AuditAction.PLATFORM_SETTING_CHANGED).exists())

    def test_changed_trial_length_applies_to_the_next_registration(self):
        self.client.patch(f"{BASE}/settings/", {"trial_duration_days": 21})
        school = make_school("Fresh")
        self.assertEqual((school.subscription.trial_end - school.subscription.trial_start).days, 21)


class NotifyAndDashboardTests(TestCase):
    def setUp(self):
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)
        self.school = make_school("Alpha")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        make_user(self.school, Role.TEACHER)

    def test_notify_reaches_only_the_school_admins_and_is_audited(self):
        response = self.client.post(f"{BASE}/schools/{self.school.id}/notify/", {"title": "Maintenance tonight", "body": "10pm-11pm", "severity": "WARNING"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"]["recipients"], 1)
        note = Notification.objects.get(type=NotificationType.ANNOUNCEMENT)
        self.assertEqual((note.recipient_id, note.severity, note.title), (self.admin.id, "WARNING", "Maintenance tonight"))
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PLATFORM_NOTIFICATION_SENT, school=self.school).exists())

    def test_notify_validation_and_no_recipients(self):
        url = f"{BASE}/schools/{self.school.id}/notify/"
        self.assertEqual(self.client.post(url, {"body": "no title"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"title": "x" * 121}).status_code, 400)
        self.assertEqual(self.client.post(url, {"title": "Hi", "severity": "PANIC"}).status_code, 400)
        empty = make_school("Empty")
        response = self.client.post(f"{BASE}/schools/{empty.id}/notify/", {"title": "Hi"})
        self.assertEqual((response.status_code, response.json()["code"]), (400, "no_recipients"))

    def test_lifecycle_actions_notify_the_school_admin(self):
        self.client.post(f"{BASE}/schools/{self.school.id}/suspend/", {"reason": "Unpaid invoice", "confirm": True})
        self.client.post(f"{BASE}/schools/{self.school.id}/reactivate/", {"confirm": True})
        kinds = list(Notification.objects.filter(recipient=self.admin).order_by("created_at").values_list("type", flat=True))
        self.assertEqual(kinds, [NotificationType.SCHOOL_SUSPENDED, NotificationType.SCHOOL_REACTIVATED])

    def test_dashboard_billing_sections_use_real_numbers(self):
        now = timezone.now()
        expired, paying = make_school("Expired"), make_school("Paying")
        Subscription.objects.filter(school=expired).update(trial_start=now - 20 * DAY, trial_end=now - DAY)
        self.client.post(f"{BASE}/payments/", {"school": str(paying.id), "amount": "10000", "payment_method": "CASH"})
        self.client.post(f"{BASE}/payments/", {"school": str(paying.id), "amount": "250.50", "payment_method": "JAZZCASH", "transaction_reference": "J1", "currency": "USD"})
        data = self.client.get(f"{BASE}/dashboard/").json()["data"]
        self.assertEqual(data["subscriptions"]["by_state"], {"TRIALING": 1, "ACTIVE": 1, "PAST_DUE": 0, "EXPIRED": 1, "CANCELLED": 0, "SUSPENDED": 0})
        self.assertEqual({r["currency"]: (r["last_30_days"], r["all_time"]) for r in data["revenue"]}, {"PKR": ("10000.00", "10000.00"), "USD": ("250.50", "250.50")})
        self.assertEqual(len(data["recent_payments"]), 2)
        self.assertEqual(PlatformPayment.objects.count(), 2)

    def test_dashboard_counts_expiring_subscriptions(self):
        now = timezone.now()
        Subscription.objects.filter(school=self.school).update(trial_start=now - 6 * DAY, trial_end=now + DAY)
        self.assertEqual(self.client.get(f"{BASE}/dashboard/").json()["data"]["subscriptions"]["expiring_soon"], 1)
