"""Role scoping for student data: who may see which students/guardians."""
from apps.accounts.roles import Role

FULL_VIEW_ROLES = {Role.SCHOOL_ADMIN, Role.RECEPTIONIST, Role.ACCOUNTANT}


def visible_students(user, queryset):
    """queryset is already filtered to the user's school."""
    if user.role in FULL_VIEW_ROLES:
        return queryset
    if user.role == Role.TEACHER:
        from apps.academics.models import Enrollment, EnrollmentStatus
        from apps.academics.scope import assigned_section_ids

        ids = Enrollment.objects.filter(
            school=user.school, session__is_current=True, status=EnrollmentStatus.ENROLLED,
            section_id__in=assigned_section_ids(user),
        ).values("student_id")
        return queryset.filter(pk__in=ids)
    if user.role == Role.PARENT:
        return queryset.filter(guardian_links__guardian__user=user).distinct()
    if user.role == Role.STUDENT:
        return queryset.filter(user=user)
    return queryset.none()


def visible_guardians(user, queryset):
    if user.role in (Role.SCHOOL_ADMIN, Role.RECEPTIONIST):
        return queryset
    if user.role == Role.PARENT:
        return queryset.filter(user=user)
    if user.role == Role.TEACHER:
        from apps.students.models import Student

        students = visible_students(user, Student.objects.filter(school=user.school))
        return queryset.filter(student_links__student__in=students).distinct()
    return queryset.none()


def guardian_users_by_student(school, student_ids) -> dict:
    """{student_id: [active parent User, ...]} for guardians that have a sign-in account (alerts, reminders)."""
    from .models import StudentGuardian

    result: dict = {}
    links = StudentGuardian.objects.filter(
        school=school, student_id__in=list(student_ids), guardian__user__isnull=False, guardian__user__is_active=True
    ).select_related("guardian__user")
    for link in links:
        result.setdefault(link.student_id, []).append(link.guardian.user)
    return result
