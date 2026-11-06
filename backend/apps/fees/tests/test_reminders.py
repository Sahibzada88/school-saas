from datetime import date, timedelta

from django.core import mail
from django.test import TestCase

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.notifications.models import Notification, NotificationType

URL = "/api/v1/school/fees/invoices/send-reminders/"


class FeeReminderTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.section = f.make_section(f.make_class(self.school))
        self.parent, _ = staff_client(self.school, Role.PARENT)
        self.student = f.make_student(self.school, first_name="Ali")
        self.lonely = f.make_student(self.school, first_name="Bilal")  # no parent account
        f.link_guardian(self.student, f.make_guardian(self.school, user=self.parent))
        f.link_guardian(self.lonely, f.make_guardian(self.school))
        self.overdue = f.make_invoice(self.student, f.enroll(self.student, self.section), due_date=date.today() - timedelta(days=3))
        f.make_invoice(self.lonely, f.enroll(self.lonely, self.section), due_date=date.today() - timedelta(days=1))
        f.make_invoice(self.student, None, due_date=date.today() + timedelta(days=30), period_label="future")
        f.make_invoice(self.student, None, due_date=date.today() - timedelta(days=9), period_label="paid", paid="1000.00")  # fully paid
        type(self.overdue).objects.filter(period_label="paid").update(status="PAID", paid_total=1000, balance=0)

    def test_overdue_reminder_notifies_parents_with_an_account(self):
        response = self.admin.post(URL, {"mode": "overdue"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"], {"invoices": 2, "notified": 1, "no_account": 1})
        note = Notification.objects.get(type=NotificationType.FEE_REMINDER)
        self.assertEqual((note.recipient_id, note.data["invoice"]), (self.parent.id, str(self.overdue.id)))
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.FEE_REMINDERS_SENT).exists())

    def test_sending_twice_the_same_day_does_not_duplicate(self):
        self.admin.post(URL, {"mode": "overdue"})
        again = self.admin.post(URL, {"mode": "overdue"}).json()["data"]
        self.assertEqual(again["notified"], 0)
        self.assertEqual(Notification.objects.filter(type=NotificationType.FEE_REMINDER).count(), 1)

    def test_due_soon_mode_and_validation(self):
        data = self.admin.post(URL, {"mode": "due_soon", "days": 40}).json()["data"]
        self.assertEqual(data["invoices"], 1)  # only the future invoice, within 40 days
        self.assertEqual(self.admin.post(URL, {"mode": "weekly"}).status_code, 400)
        self.assertEqual(self.admin.post(URL, {"mode": "due_soon", "days": 99}).status_code, 400)

    def test_email_is_sent_when_the_parent_has_an_address(self):
        self.admin.post(URL, {"mode": "overdue"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Ali", mail.outbox[0].body)

    def test_permissions(self):
        for role, allowed in ((Role.ACCOUNTANT, True), (Role.RECEPTIONIST, False), (Role.TEACHER, False), (Role.PARENT, False)):
            _, client = staff_client(self.school, role)
            self.assertEqual(client.post(URL, {"mode": "overdue"}).status_code == 200, allowed, role)

    def test_other_schools_invoices_are_never_touched(self):
        other = make_school("Beta")
        stranger = f.make_student(other)
        f.make_invoice(stranger, None, due_date=date.today() - timedelta(days=5))
        self.assertEqual(self.admin.post(URL, {"mode": "overdue"}).json()["data"]["invoices"], 2)
