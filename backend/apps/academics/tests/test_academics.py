from datetime import date

from django.test import TestCase

from apps.academics.models import AcademicSession, Enrollment, EnrollmentStatus, TeacherAssignment
from apps.accounts.roles import Role
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.students.models import Student

U = "/api/v1/school"


class SessionTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)

    def body(self, **kw):
        return {"name": "2027", "start_date": "2027-01-01", "end_date": "2027-12-31", **kw}

    def test_defaults_give_a_new_school_one_current_session(self):
        self.assertEqual(AcademicSession.objects.filter(school=self.school, is_current=True).count(), 1)

    def test_a_new_current_session_replaces_the_old_one(self):
        response = self.client.post(f"{U}/sessions/", self.body(is_current=True))
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(list(AcademicSession.objects.filter(school=self.school, is_current=True).values_list("name", flat=True)), ["2027"])

    def test_switching_current_via_patch(self):
        other = f.make_session(self.school)
        self.assertEqual(self.client.patch(f"{U}/sessions/{other.id}/", {"is_current": True}).status_code, 200)
        self.assertEqual(AcademicSession.objects.filter(school=self.school, is_current=True).get().id, other.id)

    def test_validation_and_duplicates(self):
        self.assertEqual(self.client.post(f"{U}/sessions/", self.body(end_date="2026-12-31")).status_code, 400)
        self.assertEqual(self.client.post(f"{U}/sessions/", self.body()).status_code, 201)
        self.assertEqual(self.client.post(f"{U}/sessions/", self.body()).status_code, 409)

    def test_only_admin_manages_but_staff_can_view(self):
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.get(f"{U}/sessions/").status_code, 200)
        self.assertEqual(teacher.post(f"{U}/sessions/", self.body()).status_code, 403)


class ClassAndSectionTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)

    def test_class_section_subject_crud_and_cross_tenant_fk_rejection(self):
        cls = self.client.post(f"{U}/classes/", {"name": "10", "level_order": 10})
        self.assertEqual(cls.status_code, 201, cls.content)
        section = self.client.post(f"{U}/sections/", {"school_class": cls.json()["data"]["id"], "name": "A", "capacity": 30})
        self.assertEqual(section.status_code, 201, section.content)
        foreign_class = f.make_class(make_school("Beta"))
        self.assertEqual(self.client.post(f"{U}/sections/", {"school_class": str(foreign_class.id), "name": "A"}).status_code, 400)
        self.assertEqual(self.client.post(f"{U}/subjects/", {"name": "Math", "code": "mth"}).json()["data"]["code"], "MTH")
        self.assertEqual(self.client.post(f"{U}/subjects/", {"name": "Maths 2", "code": "MTH"}).status_code, 409)

    def test_class_plan_limit(self):
        from apps.subscriptions.models import Plan

        self.school.subscription.plan = Plan.objects.create(name="T", slug="t", monthly_price="1", max_classes=1)
        self.school.subscription.save()
        self.assertEqual(self.client.post(f"{U}/classes/", {"name": "1"}).status_code, 201)
        self.assertEqual(self.client.post(f"{U}/classes/", {"name": "2"}).json()["code"], "plan_limit_reached")

    def test_deleting_a_class_is_soft(self):
        cls = f.make_class(self.school)
        self.assertEqual(self.client.delete(f"{U}/classes/{cls.id}/").status_code, 204)
        self.assertEqual(self.client.get(f"{U}/classes/{cls.id}/").status_code, 404)

    def test_section_listing_has_student_counts(self):
        section = f.make_section(f.make_class(self.school))
        f.enroll(f.make_student(self.school), section)
        f.enroll(f.make_student(self.school), section)
        row = next(r for r in self.client.get(f"{U}/sections/").json()["data"]["results"] if r["id"] == str(section.id))
        self.assertEqual(row["student_count"], 2)

    def test_teacher_assignments_reject_duplicates_and_foreign_objects(self):
        teacher, section = f.make_teacher(self.school), f.make_section(f.make_class(self.school))
        session = f.current_session(self.school)
        body = {"session": str(session.id), "teacher": str(teacher.id), "section": str(section.id)}
        self.assertEqual(self.client.post(f"{U}/teacher-assignments/", body).status_code, 201)
        self.assertEqual(self.client.post(f"{U}/teacher-assignments/", body).status_code, 409)  # also guards NULL subject duplicates
        foreign = f.make_teacher(make_school("Beta"))
        self.assertEqual(self.client.post(f"{U}/teacher-assignments/", {**body, "teacher": str(foreign.id)}).status_code, 400)


class EnrollmentTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.cls = f.make_class(self.school)
        self.section = f.make_section(self.cls, capacity=2)

    def enroll(self, student, **kw):
        return self.client.post(f"{U}/enrollments/", {"student": str(student.id), "section": str(self.section.id), **kw})

    def test_roll_numbers_are_allocated_and_capacity_is_enforced(self):
        students = [f.make_student(self.school) for _ in range(3)]
        first, second, third = (self.enroll(s) for s in students)
        self.assertEqual((first.status_code, first.json()["data"]["roll_number"], second.json()["data"]["roll_number"]), (201, 1, 2))
        self.assertEqual((third.status_code, third.json()["code"]), (409, "section_full"))

    def test_duplicate_enrollment_in_a_session_is_rejected(self):
        student = f.make_student(self.school)
        self.enroll(student)
        self.assertEqual(self.enroll(student).json()["code"], "already_enrolled")

    def test_validation(self):
        inactive = f.make_student(self.school, status="INACTIVE")
        self.assertEqual(self.enroll(inactive).status_code, 400)
        foreign_section = f.make_section(f.make_class(make_school("Beta")))
        response = self.client.post(f"{U}/enrollments/", {"student": str(f.make_student(self.school).id), "section": str(foreign_section.id)})
        self.assertEqual(response.status_code, 400)
        a, b = f.make_student(self.school), f.make_student(self.school)
        self.enroll(a, roll_number=7)
        self.assertEqual(self.enroll(b, roll_number=7).status_code, 400)

    def test_enrolling_needs_a_current_session(self):
        AcademicSession.objects.filter(school=self.school).update(is_current=False)
        response = self.enroll(f.make_student(self.school))
        self.assertEqual(response.status_code, 400)
        self.assertIn("session", response.json()["errors"])

    def test_moving_a_student_to_another_section_changes_the_class_too(self):
        enrollment_id = self.enroll(f.make_student(self.school)).json()["data"]["id"]
        other = f.make_section(f.make_class(self.school))
        response = self.client.patch(f"{U}/enrollments/{enrollment_id}/", {"section": str(other.id)})
        self.assertEqual(response.status_code, 200, response.content)
        enrollment = Enrollment.objects.get(pk=enrollment_id)
        self.assertEqual((enrollment.section_id, enrollment.school_class_id), (other.id, other.school_class_id))

    def test_enrollments_cannot_be_deleted_and_teachers_cannot_enroll(self):
        enrollment_id = self.enroll(f.make_student(self.school)).json()["data"]["id"]
        self.assertIn(self.client.delete(f"{U}/enrollments/{enrollment_id}/").status_code, (403, 405))
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.post(f"{U}/enrollments/", {"student": str(f.make_student(self.school).id), "section": str(self.section.id)}).status_code, 403)


class PromotionTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.session1 = f.current_session(self.school)
        self.session2 = f.make_session(self.school)
        self.from_section = f.make_section(f.make_class(self.school, level_order=9))
        self.up_section = f.make_section(f.make_class(self.school, level_order=10))
        self.students = [f.make_student(self.school) for _ in range(3)]
        self.enrollments = [f.enroll(s, self.from_section) for s in self.students]

    def body(self, **kw):
        return {
            "from_session": str(self.session1.id), "to_session": str(self.session2.id), "promote_to": str(self.up_section.id), "repeat_to": str(self.from_section.id),
            "decisions": [{"enrollment": str(e.id), "outcome": o} for e, o in zip(self.enrollments, ("PROMOTE", "REPEAT", "GRADUATE"))], **kw,
        }

    def test_year_end_processing(self):
        response = self.client.post(f"{U}/enrollments/promote/", self.body())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["data"], {"promoted": 1, "repeated": 1, "graduated": 1})
        old = [Enrollment.objects.get(pk=e.pk).status for e in self.enrollments]
        self.assertEqual(old, [EnrollmentStatus.PROMOTED, EnrollmentStatus.REPEATED, EnrollmentStatus.GRADUATED])
        self.assertEqual(Enrollment.objects.filter(session=self.session2).count(), 2)
        self.assertEqual(Student.objects.get(pk=self.students[2].pk).status, "GRADUATED")
        new = Enrollment.objects.get(student=self.students[0], session=self.session2)
        self.assertEqual((new.section_id, new.promoted_from_id), (self.up_section.id, self.enrollments[0].id))

    def test_validation(self):
        self.assertEqual(self.client.post(f"{U}/enrollments/promote/", self.body(to_session=str(self.session1.id))).status_code, 400)
        no_target = self.body()
        del no_target["promote_to"]
        self.assertEqual(self.client.post(f"{U}/enrollments/promote/", no_target).status_code, 400)
        self.client.post(f"{U}/enrollments/promote/", self.body())
        self.assertEqual(self.client.post(f"{U}/enrollments/promote/", self.body()).status_code, 400)  # already processed

    def test_a_failed_batch_changes_nothing(self):
        self.enrollments[1].status = EnrollmentStatus.WITHDRAWN
        self.enrollments[1].save()
        self.assertEqual(self.client.post(f"{U}/enrollments/promote/", self.body()).status_code, 400)
        self.assertEqual(Enrollment.objects.get(pk=self.enrollments[0].pk).status, EnrollmentStatus.ENROLLED)
        self.assertFalse(Enrollment.objects.filter(session=self.session2).exists())

    def test_teachers_cannot_run_year_end(self):
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.post(f"{U}/enrollments/promote/", self.body()).status_code, 403)


class TimetableTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.session = f.current_session(self.school)
        self.section_a = f.make_section(f.make_class(self.school))
        self.section_b = f.make_section(f.make_class(self.school))
        self.subject, self.teacher = f.make_subject(self.school), f.make_teacher(self.school)

    def slot(self, section, **kw):
        body = {"session": str(self.session.id), "section": str(section.id), "subject": str(self.subject.id), "teacher": str(self.teacher.id),
                "weekday": 0, "period_no": 1, "start_time": "08:00", "end_time": "08:40"}
        return self.client.post(f"{U}/timetable/", {**body, **kw})

    def test_clashes_are_rejected(self):
        self.assertEqual(self.slot(self.section_a).status_code, 201)
        self.assertEqual(self.slot(self.section_a, teacher=str(f.make_teacher(self.school).id)).status_code, 409)  # section already has a class then
        self.assertEqual(self.slot(self.section_b).status_code, 409)  # same teacher, same period, other section
        self.assertEqual(self.slot(self.section_b, period_no=2).status_code, 201)

    def test_validation(self):
        self.assertEqual(self.slot(self.section_a, end_time="07:00").status_code, 400)
        self.assertEqual(self.slot(self.section_a, weekday=9).status_code, 400)

    def test_teacher_sees_only_own_slots_and_parent_only_the_childs_section(self):
        self.slot(self.section_a)
        other_teacher = f.make_teacher(self.school)
        self.slot(self.section_b, teacher=str(other_teacher.id))
        user, teacher_client = staff_client(self.school, Role.TEACHER)
        type(self.teacher).objects.filter(pk=self.teacher.pk).update(user=user)
        self.assertEqual(len(teacher_client.get(f"{U}/timetable/").json()["data"]["results"]), 1)
        parent, parent_client = staff_client(self.school, Role.PARENT)
        child = f.make_student(self.school)
        f.enroll(child, self.section_b)
        f.link_guardian(child, f.make_guardian(self.school, user=parent))
        rows = parent_client.get(f"{U}/timetable/").json()["data"]["results"]
        self.assertEqual([r["section"] for r in rows], [str(self.section_b.id)])
