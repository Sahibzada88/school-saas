from datetime import timedelta
from itertools import product
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.core.testing import make_school
from apps.platform_admin.config import PlatformConfig
from apps.platform_admin.selectors import annotated_subscriptions
from apps.subscriptions.models import Subscription, SubscriptionStatus as S
from apps.subscriptions.state import BLOCKED, FULL, READ_ONLY, effective_state, expiring_filter, has_full_access_quick

NOW = timezone.now()
DAY = timedelta(days=1)
CFG = PlatformConfig.defaults()  # grace 5, expiring 7, trial notice 2, READ_ONLY


def sub(status, trial_end=NOW + 3 * DAY, end_date=None):
    return SimpleNamespace(status=status, trial_end=trial_end, end_date=end_date, start_date=None)


class EffectiveStateTests(SimpleTestCase):
    def test_trial_in_progress_has_full_access(self):
        eff = effective_state(sub(S.TRIALING, trial_end=NOW + 5 * DAY), NOW, CFG)
        self.assertEqual((eff.state, eff.access, eff.days_remaining, eff.is_expiring), (S.TRIALING, FULL, 5, False))

    def test_trial_expiring_flag_uses_the_notice_window(self):
        self.assertTrue(effective_state(sub(S.TRIALING, trial_end=NOW + 2 * DAY), NOW, CFG).is_expiring)
        self.assertFalse(effective_state(sub(S.TRIALING, trial_end=NOW + 2 * DAY + timedelta(hours=1)), NOW, CFG).is_expiring)

    def test_trial_expires_exactly_at_trial_end_without_any_scheduler(self):
        eff = effective_state(sub(S.TRIALING, trial_end=NOW), NOW, CFG)
        self.assertEqual((eff.state, eff.access), (S.EXPIRED, READ_ONLY))
        self.assertEqual(effective_state(sub(S.TRIALING, trial_end=NOW - timedelta(seconds=1)), NOW, CFG).state, S.EXPIRED)

    def test_active_subscription_and_expiring_window(self):
        far = effective_state(sub(S.ACTIVE, end_date=NOW + 20 * DAY), NOW, CFG)
        self.assertEqual((far.state, far.access, far.is_expiring), (S.ACTIVE, FULL, False))
        self.assertTrue(effective_state(sub(S.ACTIVE, end_date=NOW + 7 * DAY), NOW, CFG).is_expiring)
        self.assertFalse(effective_state(sub(S.ACTIVE, end_date=NOW + 8 * DAY), NOW, CFG).is_expiring)

    def test_grace_period_keeps_full_access_then_expires(self):
        at_end = effective_state(sub(S.ACTIVE, end_date=NOW), NOW, CFG)
        self.assertEqual((at_end.state, at_end.access, at_end.in_grace, at_end.days_remaining), (S.PAST_DUE, FULL, True, 5))
        inside = effective_state(sub(S.ACTIVE, end_date=NOW - 4 * DAY), NOW, CFG)
        self.assertEqual(inside.state, S.PAST_DUE)
        over = effective_state(sub(S.PAST_DUE, end_date=NOW - 5 * DAY), NOW, CFG)
        self.assertEqual((over.state, over.access), (S.EXPIRED, READ_ONLY))

    def test_zero_grace_expires_at_the_end_date(self):
        cfg = PlatformConfig(past_due_grace_days=0)
        self.assertEqual(effective_state(sub(S.ACTIVE, end_date=NOW), NOW, cfg).state, S.EXPIRED)

    def test_paid_status_without_end_date_fails_closed(self):
        self.assertEqual(effective_state(sub(S.ACTIVE, end_date=None), NOW, CFG).state, S.EXPIRED)

    def test_extended_past_due_subscription_is_active_again(self):
        self.assertEqual(effective_state(sub(S.PAST_DUE, end_date=NOW + 10 * DAY), NOW, CFG).state, S.ACTIVE)

    def test_cancelled_keeps_access_until_the_paid_period_ends(self):
        during = effective_state(sub(S.CANCELLED, end_date=NOW + 3 * DAY), NOW, CFG)
        self.assertEqual((during.state, during.access), (S.CANCELLED, FULL))
        after = effective_state(sub(S.CANCELLED, end_date=NOW - DAY), NOW, CFG)
        self.assertEqual((after.state, after.access), (S.EXPIRED, READ_ONLY))

    def test_suspended_is_blocked_whatever_the_dates_say(self):
        eff = effective_state(sub(S.SUSPENDED, trial_end=NOW + 30 * DAY, end_date=NOW + 30 * DAY), NOW, CFG)
        self.assertEqual((eff.state, eff.access), (S.SUSPENDED, BLOCKED))

    def test_persisted_expired_stays_expired(self):
        self.assertEqual(effective_state(sub(S.EXPIRED, end_date=NOW + 30 * DAY), NOW, CFG).state, S.EXPIRED)

    def test_blocked_expired_access_mode(self):
        cfg = PlatformConfig(expired_access_mode="BLOCKED")
        self.assertEqual(effective_state(sub(S.TRIALING, trial_end=NOW - DAY), NOW, cfg).access, BLOCKED)

    def test_quick_path_only_claims_full_access_when_certain(self):
        self.assertTrue(has_full_access_quick(sub(S.TRIALING, trial_end=NOW + DAY), NOW))
        self.assertTrue(has_full_access_quick(sub(S.ACTIVE, end_date=NOW + DAY), NOW))
        self.assertFalse(has_full_access_quick(sub(S.ACTIVE, end_date=NOW - DAY), NOW))  # grace needs settings
        self.assertFalse(has_full_access_quick(sub(S.SUSPENDED, trial_end=NOW + DAY, end_date=NOW + DAY), NOW))
        self.assertFalse(has_full_access_quick(sub(S.CANCELLED, end_date=NOW + DAY), NOW))


class PythonAndSqlAgreeTests(TestCase):
    """The SQL CASE used for lists/filters must give exactly the Python answer for every combination."""

    def test_every_combination(self):
        offsets = [None, -10 * DAY, -3 * DAY, timedelta(0), 3 * DAY, 10 * DAY]
        trial_ends = [-DAY, DAY]
        combos = list(product(S.values, trial_ends, offsets))
        for index, (status, trial_offset, end_offset) in enumerate(combos):
            school = make_school(f"S{index}")
            trial_end = NOW + trial_offset
            Subscription.objects.filter(school=school).update(
                status=status, trial_end=trial_end, trial_start=trial_end - 30 * DAY,
                start_date=None if end_offset is None else NOW - 60 * DAY,
                end_date=None if end_offset is None else NOW + end_offset,
            )
        for cfg in (CFG, PlatformConfig(past_due_grace_days=0), PlatformConfig(past_due_grace_days=12)):
            expiring_ids = set(Subscription.objects.filter(expiring_filter(NOW, cfg)).values_list("pk", flat=True))
            for row in annotated_subscriptions(NOW, cfg):
                eff = effective_state(row, NOW, cfg)
                self.assertEqual(row.effective, eff.state, (row.status, row.trial_end - NOW, row.end_date and row.end_date - NOW, cfg))
                self.assertEqual(row.pk in expiring_ids, eff.is_expiring, (row.status, cfg))
