import logging

from apps.notifications.models import NotificationType, Severity
from apps.notifications.services import NotificationService
from apps.students.models import Student
from apps.students.scope import guardian_users_by_student

logger = logging.getLogger(__name__)


def notify_absences(school, student_ids, day) -> int:
    """In-app notification (+ email when configured) to the parents who have an account. Once per student per day."""
    try:
        users_by_student = guardian_users_by_student(school, student_ids)
        students = {s.id: s for s in Student.objects.filter(school=school, id__in=list(users_by_student))}
        count = 0
        for student_id, users in users_by_student.items():
            student = students.get(student_id)
            if student is None:
                continue
            count += NotificationService.notify_users(
                school, users, type=NotificationType.ABSENCE_ALERT, title=f"{student.first_name} was marked absent",
                body=f"{student.full_name} was marked absent on {day:%d %b %Y}.", severity=Severity.WARNING,
                data={"student": str(student.id), "date": day.isoformat()}, dedupe_key=f"ABSENT:{student.id}:{day.isoformat()}",
                email_template="absence_alert", email_context={"student": student.full_name, "date": f"{day:%d %b %Y}"},
            )
        return count
    except Exception:  # an alert problem must never break attendance
        logger.exception("Absence alert failed")
        return 0
