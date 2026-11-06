from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.exceptions import Conflict
from apps.core.testing import api_client, make_school, make_user
from apps.notifications.models import Notification, NotificationType
from apps.platform_admin.models import PlatformSetting
from apps.subscriptions.models import Plan, Subscription, SubscriptionEvent, SubscriptionStatus as S
from apps.subscriptions.services import SubscriptionService, add_months

DAY = timedelta(days=1)


def make_plan(slug="standard", **fields):
    defaults = dict(name=slug.title(), monthly_price="1000.00", currency="PKR")
    return Plan.objects.create(slug=slug, **{**defaults, **fields})


class AddMonthsTests(SimpleTestCase):
    def test_calendar_aware(self):
        utc = dt_timezone.utc
        self.assertEqual(add_months(datetime(2026, 1, 31, 9, tzinfo=utc), 1), datetime(2026, 2, 28, 9, tzinfo=utc))
        self.assertEqual(add_months(datetime(2028, 1, 31, tzinfo=utc), 1), datetime(2028, 2, 29, tzinfo=utc))
        self.assertEqual(add_months(datetime(2026, 12, 15, tzinfo=utc), 1), datetime(2027, 1, 15, tzinfo=utc))
        self.assertEqual(add_months(datetime(2026, 3, 10, tzinfo=utc), 12), datetime(2027, 3, 10, tzinfo=utc))
        self.assertEqual(add_months(datetime(2026, 3, 10, tzinfo=utc), 25), datetime(2028, 4, 10, tzinfo=utc))


class TrialTests(TestCase):
    def test_default_trial_is_seven_days_with_no_plan(self):
        sub = make_school().subscription
        self.assertEqual(sub.status, S.TRIALING)
        self.assertEqual((sub.trial_end - sub.trial_start).days, 7)
        self.assertIsNone(sub.plan)
        self.assertTrue(SubscriptionEvent.objects.filter(subscription=sub, event_type="TRIAL_STARTED").exists())

    def test_trial_duration_and_plan_come_from_platform_settings(self):
        plan = make_plan("standard")
        PlatformSetting.objects.create(key="trial_duration_days", value=14)
        PlatformSetting.objects.create(key="trial_plan_slug", value="standard")
        school = make_school()
        sub = school.subscription
        self.assertEqual((sub.trial_end - sub.trial_start).days, 14)
        self.assertEqual(sub.plan_id, plan.id)

    def test_invalid_setting_values_fall_back_to_defaults(self):
        PlatformSetting.objects.create(key="trial_duration_days", value="lots")
        PlatformSetting.objects.create(key="trial_plan_slug", value="does-not-exist")
        sub = make_school().subscription
        self.assertEqual((sub.trial_end - sub.trial_start).days, 7)
        self.assertIsNone(sub.plan)

    def test_registration_api_starts_a_trial_and_welcomes_the_admin(self):
        PlatformSetting.objects.create(key="trial_duration_days", value=10)
        response = api_client().post("/api/v1/auth/register/", {
            "school_name": "Trial School", "admin_name": "Ayesha Khan", "email": "ayesha@trial.test",
            "phone": "", "password": "Str0ng-Test-Pass#2026", "country": "Pakistan", "city": "Lahore",
        })
        self.assertEqual(response.status_code, 201, response.content)
        sub = Subscription.objects.get(school__name="Trial School")
        self.assertEqual((sub.status, (sub.trial_end - sub.trial_start).days), (S.TRIALING, 10))
        self.assertTrue(Notification.objects.filter(recipient__email="ayesha@trial.test", type=NotificationType.TRIAL_STARTED).exists())
        data = response.json()["data"]["subscription"]
        self.assertEqual((data["state"], data["access"], data["is_trial"]), (S.TRIALING, "FULL", True))


class SyncTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.teacher = make_user(self.school, Role.TEACHER)
        self.now = timezone.now()

    def set_sub(self, **fields):
        Subscription.objects.filter(school=self.school).update(**fields)

    def notices(self, kind):
        return Notification.objects.filter(school=self.school, type=kind)

    def test_expired_trial_is_persisted_once_with_one_notification_per_admin(self):
        self.set_sub(trial_start=self.now - 9 * DAY, trial_end=self.now - DAY)
        for _ in range(3):
            sub, eff = SubscriptionService.sync(self.school)
        self.assertEqual(eff.state, S.EXPIRED)
        self.assertEqual(Subscription.objects.get(school=self.school).status, S.EXPIRED)
        self.assertEqual(SubscriptionEvent.objects.filter(subscription=sub, event_type="STATE_CHANGED").count(), 1)
        self.assertEqual(self.notices(NotificationType.TRIAL_EXPIRED).count(), 1)
        self.assertEqual(self.notices(NotificationType.TRIAL_EXPIRED).get().recipient_id, self.admin.id)  # never the teacher

    def test_trial_expiring_notice_is_sent_once(self):
        self.set_sub(trial_start=self.now - 5 * DAY, trial_end=self.now + DAY)
        SubscriptionService.sync(self.school)
        SubscriptionService.sync(self.school)
        self.assertEqual(self.notices(NotificationType.TRIAL_EXPIRING).count(), 1)

    def test_no_notice_when_nothing_is_due(self):
        SubscriptionService.sync(self.school)
        self.assertFalse(self.notices(NotificationType.TRIAL_EXPIRING).exists())
        self.assertFalse(self.notices(NotificationType.TRIAL_EXPIRED).exists())

    def test_paid_subscription_expiring_then_past_due(self):
        self.set_sub(status=S.ACTIVE, start_date=self.now - 30 * DAY, end_date=self.now + 3 * DAY)
        SubscriptionService.sync(self.school)
        self.assertEqual(self.notices(NotificationType.SUBSCRIPTION_EXPIRING).count(), 1)

        self.set_sub(end_date=self.now - DAY)
        sub, eff = SubscriptionService.sync(self.school)
        self.assertEqual((eff.state, sub.status), (S.PAST_DUE, S.PAST_DUE))
        self.assertEqual(self.notices(NotificationType.SUBSCRIPTION_EXPIRED).count(), 1)
        SubscriptionService.sync(self.school)
        self.assertEqual(self.notices(NotificationType.SUBSCRIPTION_EXPIRED).count(), 1)

        self.set_sub(end_date=self.now - 10 * DAY)
        sub, eff = SubscriptionService.sync(self.school)
        self.assertEqual((eff.state, sub.status), (S.EXPIRED, S.EXPIRED))

    def test_sync_never_touches_suspended_or_healthy_subscriptions(self):
        self.set_sub(status=S.SUSPENDED, trial_end=self.now - DAY, trial_start=self.now - 8 * DAY)
        SubscriptionService.sync(self.school)
        self.assertEqual(Subscription.objects.get(school=self.school).status, S.SUSPENDED)

    def test_summary_for_a_school_without_a_subscription_is_none(self):
        from apps.tenants.models import School

        orphan = School.objects.create(name="Orphan", slug="orphan-x", email="o@o.test", country="PK", city="X")
        self.assertIsNone(SubscriptionService.summary(orphan))


class OperationsTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.sub = self.school.subscription
        self.now = timezone.now()

    def reload(self):
        return Subscription.objects.get(pk=self.sub.pk)

    def call(self, name, **kwargs):
        return getattr(SubscriptionService, name)(subscription_id=self.sub.pk, actor=self.root, request=None, **kwargs)

    def test_extend_trial_adds_to_the_later_of_trial_end_and_now(self):
        before = self.reload().trial_end
        self.call("extend_trial", days=5, reason="Onboarding help")
        self.assertEqual(self.reload().trial_end, before + 5 * DAY)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.SUBSCRIPTION_TRIAL_EXTENDED, school=self.school).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.admin, type=NotificationType.SUBSCRIPTION_EXTENDED).exists())

    def test_extending_an_expired_trial_revives_it_from_now(self):
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.EXPIRED, trial_start=self.now - 20 * DAY, trial_end=self.now - 10 * DAY)
        self.call("extend_trial", days=7, reason="Second chance")
        sub = self.reload()
        self.assertEqual(sub.status, S.TRIALING)
        self.assertAlmostEqual((sub.trial_end - self.now).total_seconds(), 7 * 86400, delta=60)

    def test_trial_cannot_be_extended_once_the_school_has_paid(self):
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.ACTIVE, start_date=self.now, end_date=self.now + 30 * DAY)
        with self.assertRaises(Conflict):
            self.call("extend_trial", days=5, reason="Nope")

    def test_extend_subscription(self):
        end = self.now + 10 * DAY
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.ACTIVE, start_date=self.now - 20 * DAY, end_date=end)
        self.call("extend_subscription", days=15, reason="Goodwill")
        self.assertEqual(self.reload().end_date, end + 15 * DAY)

    def test_extending_a_lapsed_subscription_counts_from_now(self):
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.EXPIRED, start_date=self.now - 90 * DAY, end_date=self.now - 30 * DAY)
        self.call("extend_subscription", days=10, reason="Grace")
        sub = self.reload()
        self.assertEqual(sub.status, S.ACTIVE)
        self.assertAlmostEqual((sub.end_date - self.now).total_seconds(), 10 * 86400, delta=60)

    def test_extending_a_subscription_that_never_paid_is_refused(self):
        with self.assertRaises(Conflict):
            self.call("extend_subscription", days=5, reason="x" * 3)

    def test_change_plan_rules(self):
        basic, retired = make_plan("basic"), make_plan("old", is_active=False)
        self.call("change_plan", plan=basic, reason="Upgrade")
        self.assertEqual(self.reload().plan_id, basic.id)
        event = SubscriptionEvent.objects.get(subscription=self.sub, event_type="PLAN_CHANGED")
        self.assertEqual((event.from_plan_id, event.to_plan_id), (None, basic.id))
        with self.assertRaises(Conflict):
            self.call("change_plan", plan=basic, reason="")
        with self.assertRaises(ValidationError):
            self.call("change_plan", plan=retired, reason="")

    def test_cancel_only_paid_subscriptions_and_access_continues_until_the_end(self):
        with self.assertRaises(Conflict):
            self.call("cancel", reason="Closing")  # still on trial
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.ACTIVE, start_date=self.now, end_date=self.now + 20 * DAY)
        self.call("cancel", reason="School closing")
        sub = self.reload()
        self.assertEqual(sub.status, S.CANCELLED)
        self.assertIsNotNone(sub.cancelled_at)
        _, eff = SubscriptionService.sync(self.school)
        self.assertEqual((eff.state, eff.access), (S.CANCELLED, "FULL"))

    def test_suspend_and_resume(self):
        with self.assertRaises(Conflict):
            self.call("resume", reason="")
        self.call("suspend", reason="Chargeback")
        self.assertEqual(self.reload().status, S.SUSPENDED)
        with self.assertRaises(Conflict):
            self.call("suspend", reason="again")
        self.call("resume", reason="Resolved")
        self.assertEqual(self.reload().status, S.TRIALING)  # never paid -> back to its trial

    def test_resume_of_a_paid_subscription_restores_active(self):
        Subscription.objects.filter(pk=self.sub.pk).update(status=S.SUSPENDED, start_date=self.now - DAY, end_date=self.now + 20 * DAY)
        self.call("resume", reason="Resolved")
        self.assertEqual(self.reload().status, S.ACTIVE)

    def test_suspended_subscription_cannot_be_extended(self):
        self.call("suspend", reason="Chargeback")
        with self.assertRaises(Conflict):
            self.call("extend_trial", days=3, reason="x" * 3)
