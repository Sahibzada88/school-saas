"""Roles and the code-defined role -> permission registry (versioned in git, no DB reads per request).

The frontend receives the caller's permission list from /auth/me, so there is no second copy to keep in sync.
`scoped` permissions (teacher: own sections, parent: own children, ...) only grant the capability; the data
scope is enforced by the queryset layer of each resource in later phases.
"""
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    SCHOOL_ADMIN = "SCHOOL_ADMIN", "School Admin"
    TEACHER = "TEACHER", "Teacher"
    ACCOUNTANT = "ACCOUNTANT", "Accountant"
    RECEPTIONIST = "RECEPTIONIST", "Receptionist"
    PARENT = "PARENT", "Parent"
    STUDENT = "STUDENT", "Student"


SCHOOL_ROLES = [r for r in Role.values if r != Role.SUPER_ADMIN]


class P:
    """Permission codes."""

    # platform
    PLATFORM_DASHBOARD = "platform.dashboard.view"
    PLATFORM_SCHOOLS = "platform.schools.manage"
    PLATFORM_PLANS = "platform.plans.manage"
    PLATFORM_SUBSCRIPTIONS = "platform.subscriptions.manage"
    PLATFORM_PAYMENTS = "platform.payments.manage"
    PLATFORM_AUDIT = "platform.audit.view"
    PLATFORM_SETTINGS = "platform.settings.manage"
    PLATFORM_TENANT_DATA = "platform.tenant_data.view"  # read-only, audited
    # school
    SCHOOL_DASHBOARD = "school.dashboard.view"
    SCHOOL_SUBSCRIPTION_VIEW = "school.subscription.view"
    SCHOOL_SETTINGS = "school.settings.manage"
    SCHOOL_USERS = "school.users.manage"
    SCHOOL_AUDIT = "school.audit.view"
    # people
    STUDENTS_VIEW = "students.view"
    STUDENTS_MANAGE = "students.manage"
    STUDENTS_LIFECYCLE = "students.lifecycle"  # promote / transfer / graduate / delete
    GUARDIANS_MANAGE = "guardians.manage"
    TEACHERS_VIEW = "teachers.view"
    TEACHERS_MANAGE = "teachers.manage"
    # academics
    ACADEMICS_VIEW = "academics.view"
    ACADEMICS_MANAGE = "academics.manage"
    TIMETABLE_VIEW = "timetable.view"
    TIMETABLE_MANAGE = "timetable.manage"
    # attendance
    ATTENDANCE_STUDENTS_MARK = "attendance.students.mark"
    ATTENDANCE_STUDENTS_VIEW = "attendance.students.view"
    ATTENDANCE_TEACHERS_MANAGE = "attendance.teachers.manage"
    ATTENDANCE_TEACHERS_VIEW = "attendance.teachers.view"
    # exams
    EXAMS_MANAGE = "exams.manage"
    MARKS_ENTER = "marks.enter"
    RESULTS_PUBLISH = "results.publish"
    RESULTS_VIEW = "results.view"
    # fees
    FEES_MANAGE = "fees.manage"
    FEES_PAYMENTS_RECORD = "fees.payments.record"
    FEES_REVERSE = "fees.reverse"
    FEES_VIEW = "fees.view"
    # reports / exports
    REPORTS_VIEW = "reports.view"
    EXPORT_STUDENTS = "exports.students"
    EXPORT_TEACHERS = "exports.teachers"
    EXPORT_ATTENDANCE = "exports.attendance"
    EXPORT_FEES = "exports.fees"
    EXPORT_EXAMS = "exports.exams"
    IMAGES_VIEW = "images.view"
    # communication
    ANNOUNCEMENTS_VIEW = "announcements.view"
    ANNOUNCEMENTS_CREATE = "announcements.create"
    NOTIFICATIONS_VIEW = "notifications.view"


ALL_PERMISSIONS: frozenset[str] = frozenset(v for k, v in vars(P).items() if not k.startswith("_"))
PLATFORM_PERMISSIONS: frozenset[str] = frozenset(c for c in ALL_PERMISSIONS if c.startswith("platform."))

_COMMON = {P.ANNOUNCEMENTS_VIEW, P.NOTIFICATIONS_VIEW, P.IMAGES_VIEW}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.SUPER_ADMIN: frozenset(PLATFORM_PERMISSIONS | _COMMON),
    Role.SCHOOL_ADMIN: frozenset(ALL_PERMISSIONS - PLATFORM_PERMISSIONS),
    Role.TEACHER: frozenset(
        _COMMON
        | {
            P.STUDENTS_VIEW, P.TEACHERS_VIEW, P.ACADEMICS_VIEW, P.TIMETABLE_VIEW,
            P.ATTENDANCE_STUDENTS_MARK, P.ATTENDANCE_STUDENTS_VIEW, P.ATTENDANCE_TEACHERS_VIEW,
            P.MARKS_ENTER, P.RESULTS_VIEW, P.REPORTS_VIEW,
            P.EXPORT_ATTENDANCE, P.EXPORT_EXAMS, P.ANNOUNCEMENTS_CREATE,
        }
    ),
    Role.ACCOUNTANT: frozenset(
        _COMMON
        | {
            P.STUDENTS_VIEW, P.ACADEMICS_VIEW, P.FEES_MANAGE, P.FEES_PAYMENTS_RECORD,
            P.FEES_REVERSE, P.FEES_VIEW, P.REPORTS_VIEW, P.EXPORT_FEES,
        }
    ),
    Role.RECEPTIONIST: frozenset(
        _COMMON
        | {
            P.STUDENTS_VIEW, P.STUDENTS_MANAGE, P.GUARDIANS_MANAGE, P.TEACHERS_VIEW,
            P.ACADEMICS_VIEW, P.TIMETABLE_VIEW, P.ATTENDANCE_STUDENTS_VIEW,
            P.ATTENDANCE_TEACHERS_MANAGE, P.EXPORT_STUDENTS, P.FEES_PAYMENTS_RECORD, P.FEES_VIEW,
        }
    ),
    Role.PARENT: frozenset(
        _COMMON
        | {
            P.STUDENTS_VIEW, P.GUARDIANS_MANAGE, P.ACADEMICS_VIEW, P.TIMETABLE_VIEW,
            P.ATTENDANCE_STUDENTS_VIEW, P.RESULTS_VIEW, P.FEES_VIEW,
        }
    ),
    Role.STUDENT: frozenset(
        _COMMON
        | {
            P.STUDENTS_VIEW, P.ACADEMICS_VIEW, P.TIMETABLE_VIEW,
            P.ATTENDANCE_STUDENTS_VIEW, P.RESULTS_VIEW, P.FEES_VIEW,
        }
    ),
}
