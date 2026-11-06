from django.test import SimpleTestCase

from apps.accounts.roles import ALL_PERMISSIONS, P, PLATFORM_PERMISSIONS, ROLE_PERMISSIONS, Role


class RoleRegistryTests(SimpleTestCase):
    def test_every_role_has_an_entry_and_only_known_codes(self):
        self.assertEqual(set(ROLE_PERMISSIONS), set(Role.values))
        for role, codes in ROLE_PERMISSIONS.items():
            self.assertLessEqual(codes, ALL_PERMISSIONS, role)

    def test_platform_permissions_belong_to_super_admin_only(self):
        for role, codes in ROLE_PERMISSIONS.items():
            if role == Role.SUPER_ADMIN:
                self.assertEqual(codes & PLATFORM_PERMISSIONS, PLATFORM_PERMISSIONS)
            else:
                self.assertFalse(codes & PLATFORM_PERMISSIONS, role)

    def test_super_admin_has_no_direct_tenant_data_permissions(self):
        tenant_codes = ALL_PERMISSIONS - PLATFORM_PERMISSIONS - {P.ANNOUNCEMENTS_VIEW, P.NOTIFICATIONS_VIEW, P.IMAGES_VIEW}
        self.assertFalse(ROLE_PERMISSIONS[Role.SUPER_ADMIN] & tenant_codes)

    def test_only_school_admin_manages_school_users_and_settings(self):
        for role in Role.values:
            has = P.SCHOOL_USERS in ROLE_PERMISSIONS[role]
            self.assertEqual(has, role == Role.SCHOOL_ADMIN, role)
            self.assertEqual(P.SCHOOL_SETTINGS in ROLE_PERMISSIONS[role], role == Role.SCHOOL_ADMIN, role)

    def test_school_admin_has_every_school_level_permission(self):
        self.assertEqual(ROLE_PERMISSIONS[Role.SCHOOL_ADMIN], ALL_PERMISSIONS - PLATFORM_PERMISSIONS)

    def test_parents_and_students_cannot_write(self):
        writers = {
            P.STUDENTS_MANAGE, P.TEACHERS_MANAGE, P.ACADEMICS_MANAGE, P.EXAMS_MANAGE, P.MARKS_ENTER,
            P.FEES_MANAGE, P.FEES_PAYMENTS_RECORD, P.ATTENDANCE_STUDENTS_MARK, P.SCHOOL_USERS,
        }
        for role in (Role.PARENT, Role.STUDENT):
            self.assertFalse(ROLE_PERMISSIONS[role] & writers, role)
