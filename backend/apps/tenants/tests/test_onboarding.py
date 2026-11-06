from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.audit_logs.models import AuditLog
from apps.core.testing import TEST_PASSWORD, make_school, make_user
from apps.tenants.models import School, SchoolSettings
from apps.tenants.services import SchoolOnboardingService

DATA = dict(
    school_name="Green Valley School",
    admin_name="Bilal Ahmed",
    email="bilal@gv.test",
    phone="",
    password=TEST_PASSWORD,
    country="Pakistan",
    city="Lahore",
)


class OnboardingServiceTests(TestCase):
    def test_creates_school_settings_admin_and_audit_atomically(self):
        school, user = SchoolOnboardingService.register(**DATA)
        self.assertEqual(user.school_id, school.id)
        self.assertEqual(user.role, Role.SCHOOL_ADMIN)
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertTrue(SchoolSettings.objects.filter(school=school).exists())
        self.assertEqual(AuditLog.objects.filter(school=school).count(), 1)

    def test_same_school_name_gets_a_distinct_slug(self):
        first, _ = SchoolOnboardingService.register(**DATA)
        second, _ = SchoolOnboardingService.register(**{**DATA, "email": "other@gv.test"})
        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith(first.slug))

    def test_non_latin_names_still_get_a_slug(self):
        school, _ = SchoolOnboardingService.register(**{**DATA, "school_name": "مدرسہ"})
        self.assertTrue(school.slug)

    def test_failure_rolls_everything_back(self):
        make_user(make_school("Existing"), email="bilal@gv.test")
        schools_before, settings_before = School.objects.count(), SchoolSettings.objects.count()
        with self.assertRaises(ValidationError):
            SchoolOnboardingService.register(**DATA)
        self.assertEqual(School.objects.count(), schools_before)
        self.assertEqual(SchoolSettings.objects.count(), settings_before)
        self.assertEqual(User.objects.filter(email="bilal@gv.test").count(), 1)

    def test_single_word_admin_name(self):
        _, user = SchoolOnboardingService.register(**{**DATA, "admin_name": "Bilal"})
        self.assertEqual((user.first_name, user.last_name), ("Bilal", ""))
