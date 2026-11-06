from django.db.models import Q

from apps.accounts.roles import Role

from .models import AcademicSession, TeacherAssignment


def current_session(school):
    return AcademicSession.objects.filter(school=school, is_current=True).first()


def assigned_section_ids(user):
    """Subquery of the section ids a teacher is assigned to in the CURRENT session."""
    return TeacherAssignment.objects.filter(school=user.school, teacher__user=user, session__is_current=True).values("section_id")


def can_access_section(user, section_id) -> bool:
    """School Admin: any section. Teacher: only assigned sections. Everyone else: no."""
    if user.role == Role.SCHOOL_ADMIN:
        return True
    if user.role == Role.TEACHER:
        return assigned_section_ids(user).filter(section_id=section_id).exists()
    return False


def can_teach_subject(user, section_id, subject_id) -> bool:
    """Marks entry: admin, or a teacher assigned to this section for this subject (or for all subjects)."""
    if user.role == Role.SCHOOL_ADMIN:
        return True
    if user.role != Role.TEACHER:
        return False
    return TeacherAssignment.objects.filter(
        school=user.school, teacher__user=user, session__is_current=True, section_id=section_id
    ).filter(Q(subject_id=subject_id) | Q(subject__isnull=True)).exists()
