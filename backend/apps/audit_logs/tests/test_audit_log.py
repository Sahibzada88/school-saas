from django.test import TestCase

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.audit_logs.services import AuditService
from apps.core.testing import make_school, make_user


class AuditLogTests(TestCase):
    def test_record_captures_actor_school_and_role(self):
        school = make_school()
        user = make_user(school)
        entry = AuditService.record(AuditAction.LOGIN, actor=user, entity_type="user", entity_id=user.id)
        self.assertEqual(entry.school_id, school.id)
        self.assertEqual(entry.actor_role, user.role)
        self.assertEqual(entry.entity_id, str(user.id))

    def test_entries_are_append_only(self):
        entry = AuditService.record(AuditAction.LOGIN)
        entry.description = "tampered"
        with self.assertRaises(RuntimeError):
            entry.save()
        with self.assertRaises(RuntimeError):
            entry.delete()
        self.assertEqual(AuditLog.objects.get(pk=entry.pk).description, "")
