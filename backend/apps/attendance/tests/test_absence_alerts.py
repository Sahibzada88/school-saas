from datetime import date, timedelta
from unittest import mock

from django.test import TestCase

from apps.accounts.roles import Role
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.notifications.models import Notification, NotificationType

MARK = "/api/v1/school/attendance/mark/"


class AbsenceAlertTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.section = f.make_section(f.make_class(self.school))
        self.parent_user, _ = staff_client(self.school, Role.PARENT)
        self.ali, self.bilal = f.make_student(self.school, first_name="Ali"), f.make_student(self.school, first_name="Bilal")
        for s in (self.ali, self.bilal):
            f.enroll(s, self.section)
        f.link_guardian(self.ali, f.make_guardian(self.school, user=self.parent_user))

    def mark(self, status_ali="ABSENT", day=None):
        body = {"section": str(self.section.id), "date": (day or date.today()).isoformat(),
                "records": [{"student": str(self.ali.id), "status": status_ali}, {"student": str(self.bilal.id), "status": "ABSENT"}]}
        with self.captureOnCommitCallbacks(execute=True):
            return self.admin.post(MARK, body)

    def test_parent_with_an_account_is_notified_once(self):
        self.assertEqual(self.mark().status_code, 200)
        notes = Notification.objects.filter(type=NotificationType.ABSENCE_ALERT)
        self.assertEqual(notes.count(), 1)  # Bilal has no parent account
        self.mark()  # marking again the same day must not duplicate
        self.assertEqual(notes.count(), 1)

    def test_no_alert_for_present_students_or_past_dates(self):
        self.mark(status_ali="PRESENT")
        self.assertFalse(Notification.objects.filter(type=NotificationType.ABSENCE_ALERT).exists())
        self.mark(day=date.today() - timedelta(days=2))
        self.assertFalse(Notification.objects.filter(type=NotificationType.ABSENCE_ALERT).exists())

    def test_an_alert_failure_never_breaks_attendance(self):
        with mock.patch("apps.attendance.alerts.guardian_users_by_student", side_effect=RuntimeError("boom")):
            response = self.mark()
        self.assertEqual(response.status_code, 200)
