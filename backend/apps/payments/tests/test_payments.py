from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core.testing import api_client, login_client, make_school, make_user
from apps.notifications.models import Notification, NotificationType
from apps.payments.models import PlatformPayment
from apps.subscriptions.models import Plan, Subscription, SubscriptionStatus as S
from apps.subscriptions.services import add_months

URL = "/api/v1/platform/payments/"
DAY = timedelta(days=1)


class PaymentApiTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@alpha.test")
        self.root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        self.client = login_client(self.root)
        self.now = timezone.now()

    def pay(self, **overrides):
        body = {"school": str(self.school.id), "amount": "10000.00", "payment_method": "BANK_TRANSFER", "transaction_reference": "TXN-1"}
        return self.client.post(URL, {**body, **overrides})

    def sub(self):
        return Subscription.objects.get(school=self.school)

    def test_first_payment_activates_the_subscription(self):
        response = self.pay()
        self.assertEqual(response.status_code, 201, response.content)
        sub = self.sub()
        self.assertEqual(sub.status, S.ACTIVE)
        self.assertIsNotNone(sub.start_date)
        self.assertAlmostEqual((sub.end_date - add_months(self.now, 1)).total_seconds(), 0, delta=60)
        payment = PlatformPayment.objects.get()
        self.assertEqual((payment.amount, payment.currency, payment.created_by_id, payment.gateway), (Decimal("10000.00"), "PKR", self.root.id, "MANUAL"))
        self.assertEqual(payment.subscription_id, sub.id)

    def test_activation_and_receipt_notify_the_school_admin_only(self):
        make_user(self.school, Role.TEACHER)
        self.pay()
        kinds = set(Notification.objects.filter(school=self.school).values_list("type", flat=True))
        self.assertTrue({NotificationType.SUBSCRIPTION_ACTIVATED, NotificationType.PAYMENT_RECEIVED} <= kinds)
        self.assertEqual(set(Notification.objects.filter(school=self.school).values_list("recipient_id", flat=True)), {self.admin.id})
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PAYMENT_RECORDED, school=self.school, actor=self.root).exists())

    def test_renewal_extends_from_the_current_end_date(self):
        self.pay()
        first_end = self.sub().end_date
        self.pay(transaction_reference="TXN-2", months=3)
        sub = self.sub()
        self.assertEqual(sub.end_date, add_months(first_end, 3))
        self.assertEqual(Notification.objects.filter(type=NotificationType.SUBSCRIPTION_ACTIVATED).count(), 1)  # only the first time
        second = PlatformPayment.objects.get(transaction_reference="TXN-2")
        self.assertEqual((second.period_start, second.months), (first_end, 3))

    def test_paying_after_expiry_starts_a_fresh_period_from_now(self):
        Subscription.objects.filter(school=self.school).update(
            status=S.EXPIRED, start_date=self.now - 120 * DAY, end_date=self.now - 60 * DAY
        )
        self.pay()
        sub = self.sub()
        self.assertEqual(sub.status, S.ACTIVE)
        self.assertAlmostEqual((sub.end_date - add_months(self.now, 1)).total_seconds(), 0, delta=60)

    def test_payment_on_a_cancelled_subscription_reactivates_it(self):
        Subscription.objects.filter(school=self.school).update(
            status=S.CANCELLED, cancelled_at=self.now, start_date=self.now - 30 * DAY, end_date=self.now + 5 * DAY
        )
        self.pay()
        sub = self.sub()
        self.assertEqual((sub.status, sub.cancelled_at), (S.ACTIVE, None))

    def test_a_suspended_subscription_stays_suspended(self):
        Subscription.objects.filter(school=self.school).update(status=S.SUSPENDED)
        self.pay()
        sub = self.sub()
        self.assertEqual(sub.status, S.SUSPENDED)
        self.assertIsNotNone(sub.end_date)  # the period still moves, so resuming gives the paid time
        self.assertFalse(Notification.objects.filter(type=NotificationType.SUBSCRIPTION_ACTIVATED).exists())

    def test_payment_can_change_the_plan(self):
        plan = Plan.objects.create(name="Pro", slug="pro", monthly_price="20000", currency="USD")
        response = self.pay(plan=str(plan.id))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(self.sub().plan_id, plan.id)
        self.assertEqual(PlatformPayment.objects.get().currency, "USD")  # defaults to the plan's currency

    def test_inactive_plan_is_rejected_and_nothing_is_recorded(self):
        plan = Plan.objects.create(name="Old", slug="old", monthly_price="1", is_active=False)
        response = self.pay(plan=str(plan.id))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PlatformPayment.objects.exists())
        self.assertEqual(self.sub().status, S.TRIALING)

    def test_duplicate_method_and_reference_is_rejected_atomically(self):
        self.pay()
        before_end = self.sub().end_date
        duplicate = self.pay()
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("transaction_reference", duplicate.json()["errors"])
        self.assertEqual(PlatformPayment.objects.count(), 1)
        self.assertEqual(self.sub().end_date, before_end)  # the failed attempt did not extend anything

    def test_same_reference_with_another_method_or_blank_reference_is_fine(self):
        self.assertEqual(self.pay().status_code, 201)
        self.assertEqual(self.pay(payment_method="JAZZCASH").status_code, 201)
        self.assertEqual(self.pay(payment_method="CASH", transaction_reference="").status_code, 201)
        self.assertEqual(self.pay(payment_method="CASH", transaction_reference="").status_code, 201)

    def test_validation(self):
        for override in (
            {"amount": "0"}, {"amount": "-5"}, {"amount": "abc"}, {"months": 0}, {"months": 37},
            {"payment_method": "BITCOIN"}, {"school": "00000000-0000-0000-0000-000000000000"},
            {"payment_date": (self.now + 10 * DAY).date().isoformat()}, {"currency": "RUPEES"},
        ):
            self.assertEqual(self.pay(**override).status_code, 400, override)
        self.assertFalse(PlatformPayment.objects.exists())

    def test_list_filters_and_detail(self):
        other = make_school("Beta")
        self.pay()
        self.client.post(URL, {"school": str(other.id), "amount": "5.00", "payment_method": "CASH", "payment_date": "2026-01-15"})
        rows = lambda q: self.client.get(f"{URL}?{q}").json()["data"]["results"]
        self.assertEqual(len(rows("")), 2)
        self.assertEqual(len(rows(f"school={self.school.id}")), 1)
        self.assertEqual(len(rows("method=CASH")), 1)
        self.assertEqual(len(rows("date_to=2026-02-01")), 1)
        self.assertEqual(len(rows("search=TXN-1")), 1)
        self.assertEqual(self.client.get(f"{URL}?method=BITCOIN").status_code, 400)
        self.assertEqual(self.client.get(f"{URL}?school=nope").status_code, 400)
        pid = PlatformPayment.objects.get(transaction_reference="TXN-1").id
        self.assertEqual(self.client.get(f"{URL}{pid}/").json()["data"]["school_name"], "Alpha")

    def test_payments_are_append_only(self):
        self.pay()
        pid = PlatformPayment.objects.get().id
        for method in ("patch", "put", "delete"):
            self.assertIn(getattr(self.client, method)(f"{URL}{pid}/", {"amount": "1"}).status_code, (403, 405))
        self.assertEqual(PlatformPayment.objects.get().amount, Decimal("10000.00"))

    def test_only_the_super_admin_can_record_or_read_payments(self):
        self.assertEqual(api_client().get(URL).status_code, 401)
        for role in (Role.SCHOOL_ADMIN, Role.ACCOUNTANT, Role.TEACHER):
            client = login_client(make_user(self.school, role))
            self.assertEqual(client.get(URL).status_code, 403, role)
            response = client.post(URL, {"school": str(self.school.id), "amount": "1", "payment_method": "CASH"})
            self.assertEqual(response.status_code, 403, role)
        self.assertFalse(PlatformPayment.objects.exists())
