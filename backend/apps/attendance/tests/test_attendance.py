from datetime import date, timedelta

from django.test import TestCase

from apps.accounts.roles import Role
from apps.attendance.models import StudentAttendance, TeacherAttendance
from apps.attendance.services import today_summary
from apps.attendance.stats import attendance_percentage
from apps.core import factories as f
from apps.core.testing import make_school, staff_client

U = "/api/v1/school/attendance"
TODAY = date.today().isoformat()


class PercentageTests(TestCase):
    def test_formula(self):
        self.assertEqual(attendance_percentage(2, 1, 1), 75.0)
        self.assertEqual(attendance_percentage(0, 0, 0), None)
        self.assertEqual(attendance_percentage(0, 0, 3), 0.0)
        self.assertEqual(attendance_percentage(5, 0, 0), 100.0)


class StudentAttendanceTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.section = f.make_section(f.make_class(self.school))
        self.students = [f.make_student(self.school, first_name=n) for n in ("Ali", "Bilal", "Chand")]
        self.enrollments = [f.enroll(s, self.section) for s in self.students]

    def mark(self, client=None, **kw):
        body = {"section": str(self.section.id), "date": TODAY, "records": [{"student": str(s.id), "status": "PRESENT"} for s in self.students]}
        return (client or self.admin).post(f"{U}/mark/", {**body, **kw})

    def test_roster_then_mark_then_roster_shows_marks(self):
        roster = self.admin.get(f"{U}/roster/?section={self.section.id}&date={TODAY}").json()["data"]
        self.assertEqual([r["status"] for r in roster], [None, None, None])
        self.assertEqual(self.mark().status_code, 200)
        roster = self.admin.get(f"{U}/roster/?section={self.section.id}&date={TODAY}").json()["data"]
        self.assertEqual({r["status"] for r in roster}, {"PRESENT"})

    def test_marking_again_updates_instead_of_duplicating(self):
        self.mark()
        records = [{"student": str(self.students[0].id), "status": "ABSENT", "remarks": "Sick"}]
        self.assertEqual(self.mark(records=records).status_code, 200)
        self.assertEqual(StudentAttendance.objects.filter(student=self.students[0]).count(), 1)
        row = StudentAttendance.objects.get(student=self.students[0])
        self.assertEqual((row.status, row.remarks), ("ABSENT", "Sick"))
        self.assertEqual(StudentAttendance.objects.count(), 3)

    def test_validation(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.mark(date=future).status_code, 400)
        outsider = f.make_student(self.school)
        self.assertEqual(self.mark(records=[{"student": str(outsider.id), "status": "PRESENT"}]).status_code, 400)  # not in this section
        dup = [{"student": str(self.students[0].id), "status": "PRESENT"}] * 2
        self.assertEqual(self.mark(records=dup).status_code, 400)
        self.assertEqual(self.mark(records=[{"student": str(self.students[0].id), "status": "MAYBE"}]).status_code, 400)
        self.assertEqual(self.mark(records=[]).status_code, 400)
        foreign = f.make_section(f.make_class(make_school("Beta")))
        self.assertEqual(self.mark(section=str(foreign.id)).status_code, 400)

    def test_teacher_must_be_assigned_and_has_an_edit_window(self):
        user, teacher = staff_client(self.school, Role.TEACHER)
        profile = f.make_teacher(self.school, user=user)
        self.assertEqual(self.mark(teacher).status_code, 403)  # not assigned
        self.assertEqual(teacher.get(f"{U}/roster/?section={self.section.id}").status_code, 403)
        f.assign_teacher(profile, self.section)
        self.assertEqual(self.mark(teacher).status_code, 200)
        old = (date.today() - timedelta(days=10)).isoformat()
        self.assertEqual(self.mark(teacher, date=old).status_code, 403)  # outside the 7-day window
        self.assertEqual(self.mark(date=old).status_code, 200)  # admins may correct older dates

    def test_other_roles_cannot_mark_but_receptionist_can_view(self):
        for role in (Role.RECEPTIONIST, Role.ACCOUNTANT, Role.PARENT, Role.STUDENT):
            _, client = staff_client(self.school, role)
            self.assertEqual(self.mark(client).status_code, 403, role)
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        self.assertEqual(reception.get(f"{U}/records/").status_code, 200)

    def test_monthly_summary_and_percentage(self):
        for day, status in enumerate(["PRESENT", "PRESENT", "LATE", "ABSENT", "LEAVE"], start=2):
            StudentAttendance.objects.create(
                school=self.school, student=self.students[0], enrollment=self.enrollments[0], section=self.section, date=date(2026, 3, day), status=status
            )
        data = self.admin.get(f"{U}/monthly/?section={self.section.id}&month=2026-03").json()["data"]
        row = next(s for s in data["students"] if s["student"] == str(self.students[0].id))
        self.assertEqual((row["present"], row["late"], row["absent"], row["leave"], row["percentage"]), (2, 1, 1, 1, 75.0))
        self.assertEqual(self.admin.get(f"{U}/monthly/?section={self.section.id}&month=bad").status_code, 400)
        self.assertEqual(self.admin.get(f"{U}/monthly/").status_code, 400)

    def test_parent_sees_only_their_childs_records(self):
        self.mark()
        parent, client = staff_client(self.school, Role.PARENT)
        f.link_guardian(self.students[0], f.make_guardian(self.school, user=parent))
        rows = client.get(f"{U}/records/").json()["data"]["results"]
        self.assertEqual({r["student"] for r in rows}, {str(self.students[0].id)})
        monthly = client.get(f"{U}/monthly/?student={self.students[1].id}")
        self.assertEqual(monthly.json()["data"]["students"], [])  # another family's child: empty, not leaked

    def test_dashboard_summary_uses_real_rows(self):
        self.mark(records=[{"student": str(self.students[0].id), "status": "PRESENT"}, {"student": str(self.students[1].id), "status": "ABSENT"}])
        summary = today_summary(self.school)
        self.assertEqual((summary["enrolled"], summary["marked"], summary["counts"]["ABSENT"], summary["percentage"]), (3, 2, 1, 50.0))


class TeacherAttendanceTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.teachers = [f.make_teacher(self.school) for _ in range(2)]
        _, self.reception = staff_client(self.school, Role.RECEPTIONIST)

    def test_receptionist_marks_teacher_attendance(self):
        body = {"date": TODAY, "records": [{"teacher": str(self.teachers[0].id), "status": "PRESENT", "check_in": "08:05"}, {"teacher": str(self.teachers[1].id), "status": "LEAVE"}]}
        self.assertEqual(self.reception.post(f"{U}/teachers/", body).status_code, 200)
        self.assertEqual(self.reception.post(f"{U}/teachers/", body).status_code, 200)  # idempotent
        self.assertEqual(TeacherAttendance.objects.count(), 2)
        roster = self.reception.get(f"{U}/teachers/?date={TODAY}").json()["data"]
        self.assertEqual({r["status"] for r in roster}, {"PRESENT", "LEAVE"})

    def test_validation_and_permissions(self):
        foreign = f.make_teacher(make_school("Beta"))
        self.assertEqual(self.reception.post(f"{U}/teachers/", {"date": TODAY, "records": [{"teacher": str(foreign.id), "status": "PRESENT"}]}).status_code, 400)
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.get(f"{U}/teachers/").status_code, 403)

    def test_teacher_sees_only_own_history(self):
        user, teacher = staff_client(self.school, Role.TEACHER)
        mine = f.make_teacher(self.school, user=user)
        for t in (mine, self.teachers[0]):
            TeacherAttendance.objects.create(school=self.school, teacher=t, date=date.today(), status="PRESENT")
        rows = teacher.get(f"{U}/teacher-records/").json()["data"]["results"]
        self.assertEqual({r["teacher"] for r in rows}, {str(mine.id)})
