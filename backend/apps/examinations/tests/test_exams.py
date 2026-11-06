from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.examinations.grading import band_for, percentage, rank_desc, validate_bands
from apps.examinations.models import Exam, ExamStatus, GradingScale, Mark, ReportCard

U = "/api/v1/school"


class GradingHelperTests(SimpleTestCase):
    def test_percentage_and_ranking(self):
        self.assertEqual(percentage("250", "300"), Decimal("83.33"))
        self.assertEqual(percentage("0", "0"), Decimal("0.00"))
        self.assertEqual(rank_desc({"a": Decimal(90), "b": Decimal(80), "c": Decimal(80), "d": Decimal(70)}), {"a": 1, "b": 2, "c": 2, "d": 4})

    def test_band_lookup_has_no_gaps(self):
        from types import SimpleNamespace as NS

        bands = [NS(min_percent=Decimal("90"), max_percent=Decimal("100")), NS(min_percent=Decimal("0"), max_percent=Decimal("49.99"))]
        self.assertEqual(band_for(Decimal("95"), bands).min_percent, Decimal("90"))
        self.assertEqual(band_for(Decimal("60"), bands).min_percent, Decimal("0"))  # falls into the highest band below it

    def test_band_validation(self):
        ok = [{"grade": "A", "min_percent": "50", "max_percent": "100"}, {"grade": "F", "min_percent": "0", "max_percent": "49.99"}]
        self.assertEqual(validate_bands(ok), [])
        self.assertTrue(validate_bands([{"grade": "A", "min_percent": "40", "max_percent": "100"}, ok[1]]))
        self.assertTrue(validate_bands([{"grade": "A", "min_percent": "60", "max_percent": "50"}]))
        self.assertTrue(validate_bands([{"grade": "A", "min_percent": "0", "max_percent": "120"}]))


class ExamFixture(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin_user, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.cls = f.make_class(self.school)
        self.section = f.make_section(self.cls)
        self.math, self.urdu = f.make_subject(self.school, name="Math", code="MTH"), f.make_subject(self.school, name="Urdu", code="URD")
        self.students = [f.make_student(self.school, first_name=n) for n in ("Ali", "Bilal", "Chand")]
        self.enrollments = [f.enroll(s, self.section) for s in self.students]
        self.exam = f.make_exam(self.school, name="Midterm")
        self.es_math = f.make_exam_subject(self.exam, self.cls, self.math, total=100, passing=33)
        self.es_urdu = f.make_exam_subject(self.exam, self.cls, self.urdu, total=50, passing=20)
        self.teacher_user, self.teacher = staff_client(self.school, Role.TEACHER)
        self.profile = f.make_teacher(self.school, user=self.teacher_user)
        f.assign_teacher(self.profile, self.section, subject=self.math)

    def save_marks(self, client, exam_subject, values, **kw):
        entries = [{"student": str(s.id), **({"obtained_marks": str(v)} if v is not None else {})} for s, v in zip(self.students, values)]
        return client.post(f"{U}/exams/{self.exam.id}/marks/", {"exam_subject": str(exam_subject.id), "entries": entries, **kw})

    def schedule(self):
        return self.admin.post(f"{U}/exams/{self.exam.id}/schedule/")


class ExamWorkflowTests(ExamFixture):
    def test_schedule_needs_subjects(self):
        empty = f.make_exam(self.school, name="Empty")
        self.assertEqual(self.admin.post(f"{U}/exams/{empty.id}/schedule/").json()["code"], "no_subjects")
        self.assertEqual(self.schedule().json()["data"]["status"], "SCHEDULED")
        self.assertEqual(self.schedule().status_code, 409)

    def test_marks_are_closed_until_the_exam_is_scheduled(self):
        self.assertEqual(self.save_marks(self.admin, self.es_math, [50, 60, 70]).json()["code"], "marks_closed")

    def test_teacher_marks_entry_rules(self):
        self.schedule()
        self.assertEqual(self.save_marks(self.teacher, self.es_math, [80, 70, 60]).status_code, 200)
        self.assertEqual(Exam.objects.get(pk=self.exam.pk).status, ExamStatus.MARKS_ENTRY)  # opened automatically
        self.assertEqual(self.save_marks(self.teacher, self.es_urdu, [40, 40, 40]).status_code, 403)  # not their subject
        self.assertEqual(self.save_marks(self.teacher, self.es_math, [101, 70, 60]).status_code, 400)  # over the total
        self.assertEqual(self.save_marks(self.teacher, self.es_math, [-1, 70, 60]).status_code, 400)
        outsider = f.make_exam_subject(f.make_exam(self.school), f.make_class(self.school), self.math)
        self.assertEqual(self.teacher.post(f"{U}/exams/{self.exam.id}/marks/", {"exam_subject": str(outsider.id), "entries": []}).status_code, 400)

    def test_absent_clear_and_roster(self):
        self.schedule()
        self.save_marks(self.admin, self.es_math, [80, 70, 60])
        entries = [{"student": str(self.students[0].id), "is_absent": True}, {"student": str(self.students[1].id)}]  # absent, then blank = clear
        self.assertEqual(self.admin.post(f"{U}/exams/{self.exam.id}/marks/", {"exam_subject": str(self.es_math.id), "entries": entries}).status_code, 200)
        self.assertTrue(Mark.objects.get(student=self.students[0], exam_subject=self.es_math).is_absent)
        self.assertFalse(Mark.objects.filter(student=self.students[1], exam_subject=self.es_math).exists())
        roster = self.teacher.get(f"{U}/exams/{self.exam.id}/marks/?exam_subject={self.es_math.id}").json()["data"]
        self.assertEqual([r["entered"] for r in roster["rows"]], [True, False, True])
        self.assertTrue(roster["open"])

    def test_teacher_only_gets_their_own_sections_in_the_roster(self):
        other_section = f.make_section(self.cls, name="B")
        f.enroll(f.make_student(self.school, first_name="Zed"), other_section)
        self.schedule()
        rows = self.teacher.get(f"{U}/exams/{self.exam.id}/marks/?exam_subject={self.es_math.id}").json()["data"]["rows"]
        self.assertEqual({r["section"] for r in rows}, {"A"})
        self.assertEqual(len(self.admin.get(f"{U}/exams/{self.exam.id}/marks/?exam_subject={self.es_math.id}").json()["data"]["rows"]), 4)

    def test_only_draft_exams_can_be_deleted_and_schedule_locks_after_marks(self):
        self.assertEqual(self.admin.delete(f"{U}/exams/{f.make_exam(self.school).id}/").status_code, 204)
        self.schedule()
        self.assertEqual(self.admin.delete(f"{U}/exams/{self.exam.id}/").status_code, 409)
        self.save_marks(self.admin, self.es_math, [80, 70, 60])
        self.assertEqual(self.admin.patch(f"{U}/exam-subjects/{self.es_math.id}/", {"total_marks": "50"}).json()["code"], "exam_locked")

    def test_exam_creation_defaults_the_grading_scale(self):
        response = self.admin.post(f"{U}/exams/", {"name": "Final", "session": str(self.exam.session_id), "exam_type": str(self.exam.exam_type_id)})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(str(Exam.objects.get(name="Final").grading_scale_id), str(GradingScale.objects.filter(school=self.school).first().id))


class PublishingTests(ExamFixture):
    def fill_all(self, math=(80, 80, 30), urdu=(40, 40, 45)):
        self.schedule()
        self.save_marks(self.admin, self.es_math, math)
        self.save_marks(self.admin, self.es_urdu, urdu)

    def publish(self, **body):
        return self.admin.post(f"{U}/exams/{self.exam.id}/publish/", body)

    def test_publish_computes_grades_positions_and_pass_fail(self):
        self.fill_all()
        response = self.publish()
        self.assertEqual(response.status_code, 200, response.content)
        cards = {c.student.first_name: c for c in ReportCard.objects.filter(exam=self.exam).select_related("student")}
        ali, bilal, chand = cards["Ali"], cards["Bilal"], cards["Chand"]
        self.assertEqual((ali.obtained_marks, ali.total_marks, ali.percentage, ali.grade, ali.result_status), (Decimal("120"), Decimal("150"), Decimal("80.00"), "A", "PASS"))
        self.assertEqual((ali.position_section, bilal.position_section), (1, 1))  # tie shares the position
        self.assertEqual((chand.obtained_marks, chand.percentage, chand.grade, chand.result_status, chand.position_section), (Decimal("75"), Decimal("50.00"), "D", "FAIL", 3))  # failed Math (30 < 33)
        self.assertEqual(Exam.objects.get(pk=self.exam.pk).status, ExamStatus.PUBLISHED)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.EXAM_PUBLISHED).exists())
        lines = {l["subject"]: l for l in chand.breakdown["lines"]}
        self.assertEqual((lines["Math"]["is_pass"], lines["Urdu"]["is_pass"]), (False, True))

    def test_missing_marks_block_publishing_unless_forced(self):
        self.schedule()
        self.save_marks(self.admin, self.es_math, [80, 80, 80])
        preview = self.admin.get(f"{U}/exams/{self.exam.id}/preview/").json()["data"]
        self.assertEqual({r["missing_marks"] for r in preview["results"]}, {1})
        self.assertFalse(ReportCard.objects.exists())  # previews store nothing
        blocked = self.publish()
        self.assertEqual((blocked.status_code, blocked.json()["code"]), (409, "missing_marks"))
        forced = self.publish(force=True)
        self.assertEqual(forced.json()["data"]["missing_marks_counted_absent"], 3)
        self.assertEqual(ReportCard.objects.get(student=self.students[0]).result_status, "FAIL")  # absent in Urdu

    def test_results_are_visible_to_families_only_after_publishing(self):
        parent, parent_client = staff_client(self.school, Role.PARENT)
        f.link_guardian(self.students[0], f.make_guardian(self.school, user=parent))
        self.fill_all()
        self.assertEqual(parent_client.get(f"{U}/results/").json()["data"]["results"], [])
        self.assertEqual(parent_client.get(f"{U}/exams/").json()["data"]["results"], [])  # unpublished exams are hidden too
        self.publish()
        rows = parent_client.get(f"{U}/results/").json()["data"]["results"]
        self.assertEqual({r["student_name"] for r in rows}, {self.students[0].full_name})
        other_card = ReportCard.objects.get(student=self.students[1])
        self.assertEqual(parent_client.get(f"{U}/results/{other_card.id}/").status_code, 404)
        detail = parent_client.get(f"{U}/results/{ReportCard.objects.get(student=self.students[0]).id}/").json()["data"]
        self.assertEqual((detail["grade"], len(detail["breakdown"]["lines"]), detail["school_name"]), ("A", 2, "Alpha"))

    def test_teacher_sees_results_of_their_sections_but_cannot_publish(self):
        self.fill_all()
        self.assertEqual(self.teacher.post(f"{U}/exams/{self.exam.id}/publish/").status_code, 403)
        self.assertEqual(self.teacher.get(f"{U}/exams/{self.exam.id}/preview/").status_code, 403)
        self.publish()
        self.assertEqual(len(self.teacher.get(f"{U}/results/").json()["data"]["results"]), 3)

    def test_recompute_after_changing_the_grading_scale(self):
        self.fill_all()
        self.publish()
        scale = self.exam.grading_scale
        bands = [{"grade": "Pass", "min_percent": "40", "max_percent": "100", "gpa_points": "4", "is_pass": True}, {"grade": "Fail", "min_percent": "0", "max_percent": "39.99", "gpa_points": "0", "is_pass": False}]
        self.assertEqual(self.admin.patch(f"{U}/grading-scales/{scale.id}/", {"bands": bands}).status_code, 200)
        self.assertEqual(ReportCard.objects.get(student=self.students[0]).grade, "A")  # history is a snapshot until recomputed
        self.assertEqual(self.publish().status_code, 200)
        self.assertEqual(ReportCard.objects.get(student=self.students[0]).grade, "Pass")
        self.assertEqual(ReportCard.objects.filter(exam=self.exam).count(), 3)  # updated in place, not duplicated

    def test_grading_scale_validation(self):
        bands = [{"grade": "A", "min_percent": "40", "max_percent": "100"}, {"grade": "F", "min_percent": "0", "max_percent": "49.99"}]
        scale = GradingScale.objects.filter(school=self.school).first()
        self.assertEqual(self.admin.patch(f"{U}/grading-scales/{scale.id}/", {"bands": bands}).status_code, 400)
        self.assertEqual(self.admin.post(f"{U}/grading-scales/", {"name": "Bad", "bands": bands}).status_code, 400)

    def test_transcript_lists_published_exams_for_a_student(self):
        self.fill_all()
        self.publish()
        data = self.admin.get(f"{U}/results/transcript/{self.students[0].id}/").json()["data"]
        self.assertEqual((data["student"]["name"], len(data["exams"])), (self.students[0].full_name, 1))
        self.assertEqual(self.admin.get(f"{U}/results/transcript/{f.make_student(self.school).id}/").status_code, 404)

    def test_archive_after_publish_only(self):
        self.assertEqual(self.admin.post(f"{U}/exams/{self.exam.id}/archive/").status_code, 409)
        self.fill_all()
        self.publish()
        self.assertEqual(self.admin.post(f"{U}/exams/{self.exam.id}/archive/").json()["data"]["status"], "ARCHIVED")
