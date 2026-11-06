from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.academics.models import Enrollment
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.students.models import Guardian, Student
from apps.subscriptions.models import Plan

URL = "/api/v1/school/students/import/"
HEADER = "first_name,last_name,date_of_birth,gender,phone,email,address,blood_group,class,section,guardian_name,guardian_phone,guardian_relationship\n"


def csv_file(body: str, header: str = HEADER):
    return SimpleUploadedFile("students.csv", (header + body).encode("utf-8"), content_type="text/csv")


class StudentImportTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.cls = f.make_class(self.school, name="10")
        self.section = f.make_section(self.cls, name="A", capacity=2)

    def post(self, body, dry_run=True, **kw):
        return self.client.post(URL, {"file": csv_file(body, **kw), "dry_run": "true" if dry_run else "false"}, format="multipart")

    def test_template_download(self):
        response = self.client.get("/api/v1/school/students/import-template/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content).decode("utf-8-sig").startswith("first_name,last_name"))

    def test_dry_run_writes_nothing_and_reports_ok(self):
        response = self.post("Ali,Khan,2012-05-01,MALE,,,,,10,A,Ahmed Khan,+92 300 1234567,FATHER\n")
        data = response.json()["data"]
        self.assertEqual((response.status_code, data["ok"], data["total"], data["created"]), (200, True, 1, 0))
        self.assertFalse(Student.objects.exists())

    def test_import_creates_students_guardians_and_enrollments(self):
        body = (
            "Ali,Khan,2012-05-01,m,,,,,10,A,Ahmed Khan,+92 300 1234567,FATHER\n"
            "Sara,Khan,2013-09-15,Female,,,,,10,A,Ahmed Khan,+92 300 1234567,FATHER\n"
        )
        response = self.post(body, dry_run=False)
        self.assertEqual(response.json()["data"]["created"], 2, response.content)
        self.assertEqual(Student.objects.count(), 2)
        self.assertEqual(Guardian.objects.count(), 1)  # siblings share the guardian
        self.assertEqual(Enrollment.objects.filter(section=self.section).count(), 2)
        self.assertEqual(sorted(Student.objects.values_list("student_number", flat=True)), ["STU-00001", "STU-00002"])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.STUDENTS_IMPORTED).exists())

    def test_any_bad_row_blocks_the_whole_file_and_lists_every_problem(self):
        body = (
            "Ali,Khan,2012-05-01,MALE,,,,,10,A,,,\n"
            "Bad,Row,2999-01-01,ROBOT,call me,nope,,,10,Z,Only Name,,\n"
            "Ali,Khan,2012-05-01,MALE,,,,,,,,,\n"
        )
        response = self.post(body, dry_run=False)
        data = response.json()["data"]
        self.assertFalse(data["ok"])
        self.assertEqual({e["row"] for e in data["errors"]}, {3, 4})  # row 3 invalid, row 4 duplicate of row 2
        self.assertFalse(Student.objects.exists())

    def test_existing_student_is_not_imported_twice(self):
        f.make_student(self.school, first_name="Ali", last_name="Khan", date_of_birth="2012-05-01")
        data = self.post("Ali,Khan,2012-05-01,MALE,,,,,,,,,\n").json()["data"]
        self.assertFalse(data["ok"])
        self.assertIn("already exists", data["errors"][0]["errors"][0])

    def test_capacity_is_checked_before_anything_is_saved(self):
        body = "".join(f"S{i},K,2012-05-0{i},MALE,,,,,10,A,,,\n" for i in range(1, 4))  # capacity is 2
        data = self.post(body, dry_run=False).json()["data"]
        self.assertFalse(data["ok"])
        self.assertEqual(data["errors"][0]["row"], 4)
        self.assertFalse(Student.objects.exists())

    def test_file_level_errors(self):
        self.assertEqual(self.client.post(URL, {"dry_run": "true"}, format="multipart").status_code, 400)  # no file
        self.assertEqual(self.post("x,y\n", header="first_name,last_name\n").status_code, 400)  # missing columns
        too_many = "".join(f"S{i},K,2012-05-01,MALE,,,,,,,,,\n" for i in range(501))
        self.assertEqual(self.post(too_many).status_code, 400)
        binary = SimpleUploadedFile("x.csv", b"\xff\xfe\x00bad", content_type="text/csv")
        self.assertEqual(self.client.post(URL, {"file": binary}, format="multipart").status_code, 400)

    def test_plan_limit_applies_to_the_whole_file(self):
        self.school.subscription.plan = Plan.objects.create(name="Tiny", slug="tiny", monthly_price="1", max_students=1)
        self.school.subscription.save()
        body = "A,K,2012-05-01,MALE,,,,,,,,,\nB,K,2012-05-02,MALE,,,,,,,,,\n"
        response = self.post(body, dry_run=False)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "plan_limit_reached"))
        self.assertFalse(Student.objects.exists())

    def test_permissions(self):
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        ok = reception.post(URL, {"file": csv_file("A,K,2012-05-01,MALE,,,,,,,,,\n"), "dry_run": "true"}, format="multipart")
        self.assertEqual(ok.status_code, 200)
        for role in (Role.TEACHER, Role.ACCOUNTANT, Role.PARENT):
            _, client = staff_client(self.school, role)
            response = client.post(URL, {"file": csv_file("A,K,2012-05-01,MALE,,,,,,,,,\n")}, format="multipart")
            self.assertEqual(response.status_code, 403, role)

    def test_a_school_cannot_enrol_into_another_schools_section(self):
        other = make_school("Beta")
        f.make_section(f.make_class(other, name="7"), name="Q")
        data = self.post("A,K,2012-05-01,MALE,,,,,7,Q,,,\n").json()["data"]
        self.assertFalse(data["ok"])
        self.assertIn("does not exist", data["errors"][0]["errors"][0])


class TeacherImportTests(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        _, self.client = staff_client(self.school, Role.SCHOOL_ADMIN)

    def upload(self, body, dry_run=False, header="first_name,last_name,gender,phone,email,qualification,joining_date,date_of_birth,address\n"):
        file = SimpleUploadedFile("t.csv", (header + body).encode(), content_type="text/csv")
        return self.client.post("/api/v1/school/teachers/import/", {"file": file, "dry_run": "true" if dry_run else "false"}, format="multipart")

    def test_import_and_validation(self):
        good = self.upload("Sana,Ali,FEMALE,+92 300 7654321,sana@example.com,MSc,2025-08-01,1990-04-12,Lahore\nZoya,Khan,f,,,,,,\n")
        self.assertEqual(good.json()["data"]["created"], 2, good.content)
        from apps.teachers.models import Teacher

        self.assertEqual(sorted(Teacher.objects.values_list("employee_id", flat=True)), ["EMP-0001", "EMP-0002"])
        bad = self.upload("X,Y,ROBOT,call me,nope,,,,\n")
        self.assertFalse(bad.json()["data"]["ok"])
        self.assertEqual(Teacher.objects.count(), 2)

    def test_template_and_permissions(self):
        self.assertEqual(self.client.get("/api/v1/school/teachers/import-template/").status_code, 200)
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.get("/api/v1/school/teachers/import-template/").status_code, 403)
