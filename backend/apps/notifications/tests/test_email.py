from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.roles import Role
from apps.core.testing import TEST_PASSWORD, api_client, make_school, make_user
from apps.notifications.email import send_template
from apps.notifications.models import EmailLog
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import SubscriptionService


class ProviderTests(TestCase):
    def test_sends_and_logs(self):
        self.assertTrue(send_template("trial_expiring", "admin@school.test", {"name": "Ayesha", "days": 2}))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("2 day(s)", mail.outbox[0].body)
        self.assertEqual(EmailLog.objects.get().status, "SENT")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", DEBUG=False)
    def test_unconfigured_email_is_skipped_and_logged_not_printed(self):
        self.assertFalse(send_template("trial_expired", "admin@school.test", {"name": "A"}))
        self.assertEqual(mail.outbox, [])
        log = EmailLog.objects.get()
        self.assertEqual(log.status, "SKIPPED")

    def test_provider_failure_never_propagates(self):
        with mock.patch("apps.notifications.email.DjangoMailProvider.send", side_effect=RuntimeError("smtp down")):
            self.assertFalse(send_template("welcome", "a@b.test", {"name": "A", "school": "S", "url": "u"}))
        log = EmailLog.objects.get()
        self.assertEqual((log.status, log.error), ("FAILED", "smtp down"))

    def test_every_template_renders_with_its_documented_keys(self):
        from apps.notifications.email_templates import TEMPLATES

        context = {"name": "A", "school": "S", "url": "u", "days": 3, "amount": "PKR 1", "until": "01 Jan 2027", "link": "l", "minutes": 30}
        for name in TEMPLATES:
            self.assertTrue(send_template(name, "a@b.test", context), name)


class BillingEmailTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN, email="admin@alpha.test")
        make_user(self.school, Role.TEACHER, email="teacher@alpha.test")

    def test_registration_sends_a_welcome_email(self):
        response = api_client().post("/api/v1/auth/register/", {
            "school_name": "Fresh School", "admin_name": "Sana Ali", "email": "sana@fresh.test", "phone": "",
            "password": TEST_PASSWORD, "country": "Pakistan", "city": "Lahore",
        })
        self.assertEqual(response.status_code, 201)
        welcome = [m for m in mail.outbox if m.to == ["sana@fresh.test"]]
        self.assertEqual(len(welcome), 1)
        self.assertIn("Fresh School", welcome[0].body)

    def test_expiry_notice_emails_the_admin_once_and_never_the_teacher(self):
        now = timezone.now()
        Subscription.objects.filter(school=self.school).update(trial_start=now - timedelta(days=6), trial_end=now + timedelta(hours=20))
        for _ in range(3):
            SubscriptionService.sync(self.school)
        self.assertEqual([m.to for m in mail.outbox], [["admin@alpha.test"]])

    def test_payment_confirmation_email(self):
        from apps.payments.services import PaymentService

        root = make_user(role=Role.SUPER_ADMIN, email="root@platform.test")
        PaymentService.record_payment(
            school=self.school, amount="1000.00", currency="PKR", payment_method="CASH", transaction_reference="", payment_date=timezone.now().date(),
            months=1, notes="", plan=None, actor=root, request=None,
        )
        bodies = [m.body for m in mail.outbox if m.to == ["admin@alpha.test"]]
        self.assertTrue(any("PKR 1000.00" in b for b in bodies))
