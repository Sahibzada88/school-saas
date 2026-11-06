from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.core import factories as f
from apps.core.testing import make_school, staff_client
from apps.fees.models import FeeCategory, FeePayment, StudentInvoice

U = "/api/v1/school/fees"


class FeeFixture(TestCase):
    def setUp(self):
        self.school = make_school("Alpha")
        self.admin_user, self.admin = staff_client(self.school, Role.SCHOOL_ADMIN)
        self.cls = f.make_class(self.school)
        self.section = f.make_section(self.cls)
        self.students = [f.make_student(self.school, first_name=n) for n in ("Ali", "Bilal", "Chand")]
        self.enrollments = [f.enroll(s, self.section) for s in self.students]
        tuition, exam_fee = FeeCategory.objects.get(school=self.school, code="TUI"), FeeCategory.objects.get(school=self.school, code="EXM")
        response = self.admin.post(f"{U}/structures/", {
            "name": "Monthly 10", "session": str(f.current_session(self.school).id), "school_class": str(self.cls.id), "frequency": "MONTHLY",
            "items": [{"category": str(tuition.id), "amount": "5000"}, {"category": str(exam_fee.id), "amount": "500"}],
        })
        assert response.status_code == 201, response.content
        self.structure_id = response.json()["data"]["id"]

    def generate(self, client=None, **kw):
        body = {"structure": self.structure_id, "period_label": "Oct-2026", "due_date": (date.today() + timedelta(days=10)).isoformat(), **kw}
        return (client or self.admin).post(f"{U}/invoices/generate/", body)

    def first_invoice(self):
        self.generate()
        return StudentInvoice.objects.filter(school=self.school).order_by("invoice_number").first()


class StructureAndGenerationTests(FeeFixture):
    def test_structure_total_and_validation(self):
        data = self.admin.get(f"{U}/structures/{self.structure_id}/").json()["data"]
        self.assertEqual((data["total"], len(data["items"]), data["class_name"]), ("5500.00", 2, self.cls.name))
        tuition = FeeCategory.objects.get(school=self.school, code="TUI")
        dup = {"name": "X", "session": str(f.current_session(self.school).id), "items": [{"category": str(tuition.id), "amount": "1"}] * 2}
        self.assertEqual(self.admin.post(f"{U}/structures/", dup).status_code, 400)
        foreign = FeeCategory.objects.create(school=make_school("Beta"), name="Lab", code="LAB")
        self.assertEqual(self.admin.post(f"{U}/structures/", {**dup, "items": [{"category": str(foreign.id), "amount": "1"}]}).status_code, 400)

    def test_generation_is_idempotent_and_numbers_are_sequential(self):
        first = self.generate().json()["data"]
        again = self.generate().json()["data"]
        self.assertEqual((first["created"], again["created"], again["skipped"]), (3, 0, 3))
        numbers = sorted(StudentInvoice.objects.values_list("invoice_number", flat=True))
        self.assertEqual(numbers, ["INV-00001", "INV-00002", "INV-00003"])
        invoice = StudentInvoice.objects.first()
        self.assertEqual((invoice.subtotal, invoice.total, invoice.balance, invoice.status), (Decimal("5500.00"), Decimal("5500.00"), Decimal("5500.00"), "ISSUED"))
        self.assertEqual(invoice.items.count(), 2)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.INVOICES_GENERATED).exists())

    def test_generation_only_covers_enrolled_students_and_can_target_a_section(self):
        other_section = f.make_section(self.cls, name="B")
        f.enroll(f.make_student(self.school, first_name="Zed"), other_section)
        self.assertEqual(self.generate(section=str(other_section.id)).json()["data"]["created"], 1)
        self.assertEqual(self.generate().json()["data"]["created"], 3)

    def test_validation_and_permissions(self):
        self.assertEqual(self.generate(due_date="2020-01-01").status_code, 400)
        empty = self.admin.post(f"{U}/structures/", {"name": "Empty", "session": str(f.current_session(self.school).id)}).json()["data"]["id"]
        self.assertEqual(self.admin.post(f"{U}/invoices/generate/", {"structure": empty, "period_label": "X", "due_date": "2030-01-01"}).status_code, 400)
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        self.assertEqual(self.generate(reception).status_code, 403)
        _, accountant = staff_client(self.school, Role.ACCOUNTANT)
        self.assertEqual(self.generate(accountant).status_code, 200)


class InvoiceAdjustmentTests(FeeFixture):
    def test_percent_and_fixed_discounts_and_fines(self):
        invoice = self.first_invoice()
        url = f"{U}/invoices/{invoice.id}"
        self.assertEqual(self.admin.post(f"{url}/discounts/", {"kind": "PERCENT", "value": "10", "reason": "Sibling"}).status_code, 201)
        data = self.admin.post(f"{url}/discounts/", {"kind": "FIXED", "value": "250", "reason": "Scholarship"}).json()["data"]
        self.assertEqual((data["subtotal"], data["discount_total"], data["total"]), ("5500.00", "800.00", "4700.00"))  # 550 + 250
        data = self.admin.post(f"{url}/fines/", {"amount": "100", "reason": "Late"}).json()["data"]
        self.assertEqual((data["total"], data["balance"]), ("4800.00", "4800.00"))

    def test_invalid_adjustments(self):
        invoice = self.first_invoice()
        url = f"{U}/invoices/{invoice.id}"
        self.assertEqual(self.admin.post(f"{url}/discounts/", {"kind": "PERCENT", "value": "150", "reason": "Too much"}).status_code, 400)
        self.assertEqual(self.admin.post(f"{url}/discounts/", {"kind": "FIXED", "value": "-5", "reason": "Negative"}).status_code, 400)
        self.assertEqual(self.admin.post(f"{url}/fines/", {"amount": "0", "reason": "Zero"}).status_code, 400)
        self.assertEqual(self.admin.post(f"{url}/discounts/", {"kind": "FIXED", "value": "9000", "reason": "More than owed"}).status_code, 400)  # would make total negative
        invoice.refresh_from_db()
        self.assertEqual(invoice.total, Decimal("5500.00"))

    def test_a_discount_cannot_drop_the_total_below_what_was_paid(self):
        invoice = self.first_invoice()
        self.admin.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "5000", "method": "CASH"})
        response = self.admin.post(f"{U}/invoices/{invoice.id}/discounts/", {"kind": "FIXED", "value": "1000", "reason": "Late discount"})
        self.assertEqual(response.status_code, 400)

    def test_void_rules_and_regeneration(self):
        invoice = self.first_invoice()
        pay = self.admin.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "100", "method": "CASH"}).json()["data"]["payment"]
        self.assertEqual(self.admin.post(f"{U}/invoices/{invoice.id}/void/", {"reason": "Mistake"}).json()["code"], "has_payments")
        self.admin.post(f"{U}/payments/{pay['id']}/reverse/", {"reason": "Wrong"})
        self.assertEqual(self.admin.post(f"{U}/invoices/{invoice.id}/void/", {"reason": "Mistake"}).status_code, 200)
        self.assertEqual(self.admin.post(f"{U}/invoices/{invoice.id}/void/", {"reason": "Again"}).status_code, 409)
        self.assertEqual(self.admin.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "1", "method": "CASH"}).status_code, 409)
        self.assertEqual(self.admin.post(f"{U}/invoices/{invoice.id}/fines/", {"amount": "5", "reason": "Nope"}).status_code, 409)
        regenerated = self.generate().json()["data"]
        self.assertEqual(regenerated["created"], 1)  # the voided invoice no longer blocks the period


class PaymentTests(FeeFixture):
    def test_partial_then_full_payment(self):
        invoice = self.first_invoice()
        url = f"{U}/invoices/{invoice.id}/payments/"
        first = self.admin.post(url, {"amount": "1000", "method": "CASH"})
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual((first.json()["data"]["payment"]["receipt_number"], first.json()["data"]["invoice"]["status"], first.json()["data"]["invoice"]["balance"]), ("RCT-00001", "PARTIALLY_PAID", "4500.00"))
        final = self.admin.post(url, {"amount": "4500", "method": "BANK", "reference": "TRX1"}).json()["data"]["invoice"]
        self.assertEqual((final["status"], final["balance"], final["paid_total"]), ("PAID", "0.00", "5500.00"))
        self.assertEqual(sorted(FeePayment.objects.values_list("receipt_number", flat=True)), ["RCT-00001", "RCT-00002"])

    def test_invalid_payments(self):
        invoice = self.first_invoice()
        url = f"{U}/invoices/{invoice.id}/payments/"
        for body in ({"amount": "6000", "method": "CASH"}, {"amount": "0", "method": "CASH"}, {"amount": "-1", "method": "CASH"}, {"amount": "10", "method": "BITCOIN"}, {"amount": "10", "method": "CASH", "paid_on": (date.today() + timedelta(days=2)).isoformat()}):
            self.assertEqual(self.admin.post(url, body).status_code, 400, body)
        self.assertFalse(FeePayment.objects.exists())

    def test_reversal_restores_the_balance_and_is_one_way(self):
        invoice = self.first_invoice()
        pay = self.admin.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "5500", "method": "CASH"}).json()["data"]["payment"]
        response = self.admin.post(f"{U}/payments/{pay['id']}/reverse/", {"reason": "Cheque bounced"})
        self.assertEqual((response.status_code, response.json()["data"]["status"]), (200, "REVERSED"))
        invoice.refresh_from_db()
        self.assertEqual((invoice.status, invoice.balance, invoice.paid_total), ("ISSUED", Decimal("5500.00"), Decimal("0.00")))
        self.assertEqual(self.admin.post(f"{U}/payments/{pay['id']}/reverse/", {"reason": "Again"}).status_code, 409)
        self.assertEqual(self.admin.post(f"{U}/payments/{pay['id']}/reverse/", {"reason": ""}).status_code, 400)

    def test_accountants_may_only_reverse_their_own_payments_from_today(self):
        invoice = self.first_invoice()
        accountant_user, accountant = staff_client(self.school, Role.ACCOUNTANT)
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        by_reception = reception.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "100", "method": "CASH"}).json()["data"]["payment"]
        own = accountant.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "100", "method": "CASH"}).json()["data"]["payment"]
        self.assertEqual(accountant.post(f"{U}/payments/{by_reception['id']}/reverse/", {"reason": "Not mine"}).status_code, 403)
        self.assertEqual(accountant.post(f"{U}/payments/{own['id']}/reverse/", {"reason": "Typo"}).status_code, 200)
        old = f.make_fee_payment(invoice, "50.00", received_by=accountant_user)
        FeePayment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=2))
        self.assertEqual(accountant.post(f"{U}/payments/{old.id}/reverse/", {"reason": "Old"}).status_code, 403)
        self.assertEqual(self.admin.post(f"{U}/payments/{old.id}/reverse/", {"reason": "Admin may"}).status_code, 200)

    def test_receptionist_can_record_but_not_reverse_and_teacher_sees_nothing(self):
        invoice = self.first_invoice()
        _, reception = staff_client(self.school, Role.RECEPTIONIST)
        pay = reception.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "100", "method": "CASH"})
        self.assertEqual(pay.status_code, 201)
        self.assertEqual(reception.post(f"{U}/payments/{pay.json()['data']['payment']['id']}/reverse/", {"reason": "Oops"}).status_code, 403)
        _, teacher = staff_client(self.school, Role.TEACHER)
        self.assertEqual(teacher.get(f"{U}/invoices/").status_code, 403)

    def test_audit_trail(self):
        invoice = self.first_invoice()
        pay = self.admin.post(f"{U}/invoices/{invoice.id}/payments/", {"amount": "100", "method": "CASH"}).json()["data"]["payment"]
        self.admin.post(f"{U}/payments/{pay['id']}/reverse/", {"reason": "Typo"})
        actions = set(AuditLog.objects.filter(school=self.school).values_list("action", flat=True))
        self.assertTrue({AuditAction.FEE_PAYMENT_RECORDED, AuditAction.FEE_PAYMENT_REVERSED} <= actions)


class VisibilityAndFilterTests(FeeFixture):
    def test_families_see_only_their_childrens_invoices_and_payments(self):
        self.generate()
        parent, parent_client = staff_client(self.school, Role.PARENT)
        f.link_guardian(self.students[0], f.make_guardian(self.school, user=parent))
        rows = parent_client.get(f"{U}/invoices/").json()["data"]["results"]
        self.assertEqual({r["student"]["id"] for r in rows}, {str(self.students[0].id)})
        other = StudentInvoice.objects.get(student=self.students[1])
        self.assertEqual(parent_client.get(f"{U}/invoices/{other.id}/").status_code, 404)
        self.assertEqual(parent_client.post(f"{U}/invoices/{other.id}/payments/", {"amount": "1", "method": "CASH"}).status_code, 404)
        self.assertEqual(parent_client.post(f"{U}/invoices/generate/", {}).status_code, 403)

    def test_filters_overdue_and_search(self):
        overdue = f.make_invoice(self.students[0], self.enrollments[0], due_date=date.today() - timedelta(days=5))
        f.make_invoice(self.students[1], self.enrollments[1])
        rows = lambda q: self.admin.get(f"{U}/invoices/?{q}").json()["data"]["results"]
        self.assertEqual([r["id"] for r in rows("overdue=true")], [str(overdue.id)])
        self.assertTrue(rows("overdue=true")[0]["is_overdue"])
        self.assertEqual(len(rows(f"search={self.students[1].first_name}")), 1)
        self.assertEqual(len(rows(f"student={self.students[0].id}")), 1)
        self.assertEqual(self.admin.get(f"{U}/invoices/?student=bad").status_code, 400)
