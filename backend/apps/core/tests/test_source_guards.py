"""Static guards over the source tree (cheap, fast, and they catch whole classes of mistakes)."""
import re
from pathlib import Path

from django.test import SimpleTestCase

APPS = Path(__file__).resolve().parents[2]
SCHOOL_SERIALIZER_FILES = [
    "students/serializers.py", "teachers/serializers.py", "academics/serializers.py", "attendance/serializers.py",
    "examinations/serializers.py", "fees/serializers.py", "notifications/announcements.py",
]


def source_files():
    return [p for p in APPS.rglob("*.py") if "migrations" not in p.parts and "tests" not in p.parts and p.name not in {"testing.py", "factories.py"}]


class SourceGuardTests(SimpleTestCase):
    def test_serializers_never_use_all_or_exclude(self):
        offenders = []
        for path in source_files():
            text = path.read_text()
            if re.search(r"""fields\s*=\s*["']__all__["']""", text) or re.search(r"^\s*exclude\s*=", text, re.M):
                offenders.append(str(path.relative_to(APPS)))
        self.assertEqual(offenders, [], "Use explicit field lists (mass-assignment protection).")

    def test_school_facing_serializers_never_expose_a_school_field(self):
        for name in SCHOOL_SERIALIZER_FILES:
            text = (APPS / name).read_text()
            self.assertIsNone(re.search(r"""["']school["']""", text), f"{name} exposes/accepts a 'school' field: the tenant must come from the user.")

    def test_no_raw_sql_outside_the_allowed_modules(self):
        allowed = {"core/rls.py", "core/views.py", "core/management/commands/check_rls.py"}
        offenders = []
        for path in source_files():
            rel = str(path.relative_to(APPS)).replace("\\", "/")
            if rel in allowed:
                continue
            if re.search(r"\.raw\(|\.extra\(|cursor\(\)|RawSQL", path.read_text()):
                offenders.append(rel)
        self.assertEqual(offenders, [], "Raw SQL needs review: use the ORM or add the module to the allow-list deliberately.")

    def test_no_debug_prints_or_hardcoded_secrets(self):
        offenders = []
        for path in source_files():
            text = path.read_text()
            if re.search(r"^\s*print\(", text, re.M) and "management" not in path.parts:
                offenders.append(f"{path.relative_to(APPS)}: print()")
            if re.search(r"""(SECRET_KEY|PASSWORD|API_KEY)\s*=\s*["'][^"']{12,}["']""", text) and "settings" not in path.parts:
                offenders.append(f"{path.relative_to(APPS)}: hard-coded secret")
        self.assertEqual(offenders, [])
