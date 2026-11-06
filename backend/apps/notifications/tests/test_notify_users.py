from django.core import mail
from django.test import TestCase

from apps.accounts.roles import Role
from apps.core.testing import make_school, make_user
from apps.notifications.models import Notification, NotificationType
from apps.notifications.services import NotificationService


class NotifyUsersTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.a = make_user(self.school, Role.PARENT, email="a@alpha.test")
        self.b = make_user(self.school, Role.PARENT, email="b@alpha.test")

    def send(self, users, **kw):
        return NotificationService.notify_users(self.school, users, type=NotificationType.FEE_REMINDER, title="T", **kw)

    def test_creates_one_per_user_and_dedupes_per_recipient(self):
        self.assertEqual(self.send([self.a, self.b, self.a], dedupe_key="K1"), 2)  # duplicates in the input are collapsed
        self.assertEqual(self.send([self.a, self.b], dedupe_key="K1"), 0)
        self.assertEqual(self.send([self.a], dedupe_key="K2"), 1)  # a different key is a new notification
        self.assertEqual(Notification.objects.count(), 3)

    def test_without_a_key_every_call_notifies(self):
        self.send([self.a])
        self.send([self.a])
        self.assertEqual(Notification.objects.count(), 2)

    def test_email_goes_only_to_newly_notified_users(self):
        kw = dict(dedupe_key="E1", email_template="absence_alert", email_context={"student": "Ali", "date": "01 Jan 2026"})
        self.send([self.a], **kw)
        self.send([self.a, self.b], **kw)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["a@alpha.test", "b@alpha.test"])

    def test_empty_recipient_list_is_a_noop(self):
        self.assertEqual(self.send([]), 0)
