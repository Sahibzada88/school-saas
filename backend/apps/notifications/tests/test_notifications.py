from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.core.testing import api_client, login_client, make_school, make_user
from apps.notifications.models import Notification, NotificationType, Severity
from apps.notifications.services import NotificationService
from apps.subscriptions.models import Subscription
from apps.tenants.models import School, SchoolStatus

URL = "/api/v1/notifications/"


def notify(user, title="Hello", **fields):
    return Notification.objects.create(recipient=user, school=user.school, type=NotificationType.ANNOUNCEMENT, title=title, **fields)


class NotificationApiTests(TestCase):
    def setUp(self):
        self.school, self.other = make_school("Alpha"), make_school("Beta")
        self.admin = make_user(self.school, Role.SCHOOL_ADMIN)
        self.teacher = make_user(self.school, Role.TEACHER)
        self.other_admin = make_user(self.other, Role.SCHOOL_ADMIN)
        self.client = login_client(self.admin)

    def test_requires_authentication(self):
        self.assertEqual(api_client().get(URL).status_code, 401)
        self.assertEqual(api_client().get(URL + "unread-count/").status_code, 401)

    def test_user_sees_only_their_own_notifications_newest_first(self):
        first, second = notify(self.admin, "first"), notify(self.admin, "second")
        notify(self.teacher, "teacher only")
        notify(self.other_admin, "other school")
        titles = [n["title"] for n in self.client.get(URL).json()["data"]["results"]]
        self.assertEqual(titles, ["second", "first"])
        self.assertEqual(self.client.get(URL + "unread-count/").json()["data"]["count"], 2)

    def test_mark_one_read_and_unread_filter(self):
        a, b = notify(self.admin, "a"), notify(self.admin, "b")
        response = self.client.post(f"{URL}{a.id}/read/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["is_read"])
        self.assertIsNotNone(response.json()["data"]["read_at"])
        unread = self.client.get(URL + "?unread=true").json()["data"]["results"]
        self.assertEqual([n["id"] for n in unread], [str(b.id)])
        self.assertEqual(self.client.get(URL + "unread-count/").json()["data"]["count"], 1)

    def test_mark_all_read(self):
        for i in range(3):
            notify(self.admin, f"n{i}")
        notify(self.teacher, "not mine")
        self.assertEqual(self.client.post(URL + "mark-all-read/").json()["data"]["updated"], 3)
        self.assertEqual(self.client.get(URL + "unread-count/").json()["data"]["count"], 0)
        self.assertTrue(Notification.objects.filter(recipient=self.teacher, is_read=False).exists())  # untouched

    def test_other_users_notifications_are_404(self):
        foreign = notify(self.teacher, "teacher only")
        self.assertEqual(self.client.post(f"{URL}{foreign.id}/read/").status_code, 404)
        self.assertEqual(self.client.post(f"{URL}not-a-uuid/read/").status_code, 404)
        foreign.refresh_from_db()
        self.assertFalse(foreign.is_read)

    def test_every_role_can_read_their_own(self):
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.RECEPTIONIST, Role.PARENT, Role.STUDENT):
            user = make_user(self.school, role)
            notify(user, "mine")
            self.assertEqual(len(login_client(user).get(URL).json()["data"]["results"]), 1, role)

    def test_a_suspended_schools_admin_can_still_read_why(self):
        notify(self.admin, "You were suspended", severity=Severity.CRITICAL)
        School.objects.filter(pk=self.school.pk).update(status=SchoolStatus.SUSPENDED)
        self.assertEqual(self.client.get("/api/v1/school/users/").status_code, 403)
        self.assertEqual(len(self.client.get(URL).json()["data"]["results"]), 1)

    def test_request_time_generation_without_any_worker(self):
        now = timezone.now()
        Subscription.objects.filter(school=self.school).update(trial_start=now - 6 * timedelta(days=1), trial_end=now + timedelta(hours=20))
        self.assertEqual(self.client.get(URL + "unread-count/").json()["data"]["count"], 1)  # created lazily
        for _ in range(3):
            self.client.get(URL)
            self.client.get("/api/v1/auth/me/")
        self.assertEqual(self.client.get(URL + "unread-count/").json()["data"]["count"], 1)  # and never duplicated
        self.assertEqual(Notification.objects.filter(recipient=self.admin, type=NotificationType.TRIAL_EXPIRING).count(), 1)
        self.assertFalse(Notification.objects.filter(recipient=self.teacher).exists())

    def test_platform_staff_have_their_own_empty_inbox(self):
        root = login_client(make_user(role=Role.SUPER_ADMIN, email="root@platform.test"))
        self.assertEqual(root.get(URL).json()["data"]["results"], [])


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.school = make_school()
        self.admins = [make_user(self.school, Role.SCHOOL_ADMIN) for _ in range(2)]
        make_user(self.school, Role.SCHOOL_ADMIN, is_active=False)
        make_user(self.school, Role.TEACHER)
        make_user(make_school("Other"), Role.SCHOOL_ADMIN)

    def test_goes_to_active_admins_of_that_school_only(self):
        count = NotificationService.notify_school_admins(self.school, type=NotificationType.ANNOUNCEMENT, title="Hi")
        self.assertEqual(count, 2)
        self.assertEqual(set(Notification.objects.values_list("recipient_id", flat=True)), {a.id for a in self.admins})

    def test_dedupe_key_makes_it_idempotent(self):
        for _ in range(3):
            NotificationService.notify_school_admins(self.school, type=NotificationType.TRIAL_EXPIRING, title="x", dedupe_key="K1")
        self.assertEqual(Notification.objects.count(), 2)
        NotificationService.notify_school_admins(self.school, type=NotificationType.TRIAL_EXPIRING, title="x", dedupe_key="K2")
        self.assertEqual(Notification.objects.count(), 4)

    def test_database_constraint_blocks_duplicates_even_without_the_precheck(self):
        admin = self.admins[0]
        Notification.objects.create(recipient=admin, type="ANNOUNCEMENT", title="a", dedupe_key="K")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(recipient=admin, type="ANNOUNCEMENT", title="b", dedupe_key="K")
        Notification.objects.create(recipient=admin, type="ANNOUNCEMENT", title="c")  # no key: unlimited
        Notification.objects.create(recipient=admin, type="ANNOUNCEMENT", title="d")
