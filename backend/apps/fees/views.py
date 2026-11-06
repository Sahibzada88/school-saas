from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.accounts.roles import P
from apps.core.responses import success_response
from apps.core.viewsets import TenantModelViewSet, TenantScopedViewSet
from apps.students.models import Student
from apps.students.scope import visible_students

from .models import FeeCategory, FeePayment, FeeStructure, FeeStructureItem, InvoiceStatus, StudentInvoice
from .serializers import (
    DiscountInputSerializer,
    FeeCategorySerializer,
    FeePaymentListSerializer,
    FeeStructureSerializer,
    FineInputSerializer,
    GenerateInvoicesSerializer,
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    PaymentInputSerializer,
    PaymentOut,
    ReasonSerializer,
    ReminderInputSerializer,
)
from .reminders import FeeReminderService
from .services import FeeService


class FeeCategoryViewSet(TenantModelViewSet):
    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer
    view_permission = P.FEES_VIEW
    manage_permission = P.FEES_MANAGE
    ordering = ("name",)


class FeeStructureViewSet(TenantModelViewSet):
    queryset = FeeStructure.objects.select_related("session", "school_class").prefetch_related("items__category")
    serializer_class = FeeStructureSerializer
    view_permission = P.FEES_VIEW
    manage_permission = P.FEES_MANAGE
    filter_params = {"session": "session_id", "class": "school_class_id"}
    ordering = ("name",)

    @staticmethod
    def _replace_items(structure, items):
        structure.items.all().delete()
        FeeStructureItem.objects.bulk_create([FeeStructureItem(school=structure.school, structure=structure, category=i["category"], amount=i["amount"]) for i in items])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", [])
        with transaction.atomic():
            structure = FeeStructure.objects.create(school=self.get_school(), **data)
            self._replace_items(structure, items)
        return success_response(FeeStructureSerializer(self.get_queryset().get(pk=structure.pk)).data, message="Fee structure created.", status=201)

    def partial_update(self, request, *args, **kwargs):
        structure = self.get_object()
        serializer = self.get_serializer(structure, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", None)
        with transaction.atomic():
            for field, value in data.items():
                setattr(structure, field, value)
            structure.save()
            if items is not None:
                self._replace_items(structure, items)
        return success_response(FeeStructureSerializer(self.get_queryset().get(pk=structure.pk)).data, message="Fee structure updated.")


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    queryset = StudentInvoice.objects.select_related("student", "session")
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {
        "list": P.FEES_VIEW, "retrieve": P.FEES_VIEW, "generate": P.FEES_MANAGE, "void": P.FEES_MANAGE,
        "discount": P.FEES_MANAGE, "fine": P.FEES_MANAGE, "add_payment": P.FEES_PAYMENTS_RECORD, "send_reminders": P.FEES_MANAGE,
    }

    def scope_queryset(self, queryset):
        return queryset.filter(student__in=visible_students(self.request.user, Student.objects.filter(school=self.request.user.school)))

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related("items", "discounts", "fines", "payments")
        if self.action != "list":
            return queryset
        params = self.request.query_params
        try:
            for param, lookup in {"student": "student_id", "status": "status", "session": "session_id", "period": "period_label"}.items():
                if params.get(param):
                    queryset = queryset.filter(**{lookup: params[param].strip()})
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc
        if params.get("overdue") == "true":
            queryset = queryset.filter(status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID], due_date__lt=date.today())
        search = params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(invoice_number__icontains=search) | Q(student__first_name__icontains=search) | Q(student__last_name__icontains=search) | Q(student__student_number__icontains=search))
        return queryset.order_by("-issue_date", "-invoice_number")

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceDetailSerializer

    def _detail(self, invoice_id):
        return InvoiceDetailSerializer(StudentInvoice.objects.select_related("student", "session").prefetch_related("items", "discounts", "fines", "payments").get(pk=invoice_id)).data

    @action(detail=False, methods=["post"])
    def generate(self, request):
        serializer = GenerateInvoicesSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        result = FeeService.generate_invoices(
            school=self.get_school(), structure=d["structure"], period_label=d["period_label"], issue_date=d["issue_date"],
            due_date=d["due_date"], section=d.get("section"), actor=request.user, request=request,
        )
        return success_response(result, message=f"{result['created']} invoice(s) generated.")

    @action(detail=False, methods=["post"], url_path="send-reminders")
    def send_reminders(self, request):
        serializer = ReminderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = FeeReminderService.send(school=self.get_school(), actor=request.user, request=request, **serializer.validated_data)
        return success_response(result, message=f"{result['notified']} parent(s) notified.")

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        invoice = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        FeeService.void_invoice(invoice_id=invoice.pk, reason=serializer.validated_data["reason"], actor=request.user, request=request)
        return success_response(self._detail(invoice.pk), message="Invoice voided.")

    @action(detail=True, methods=["post"], url_path="discounts")
    def discount(self, request, pk=None):
        invoice = self.get_object()
        serializer = DiscountInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        FeeService.add_discount(invoice_id=invoice.pk, actor=request.user, **serializer.validated_data)
        return success_response(self._detail(invoice.pk), message="Discount applied.", status=201)

    @action(detail=True, methods=["post"], url_path="fines")
    def fine(self, request, pk=None):
        invoice = self.get_object()
        serializer = FineInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        FeeService.add_fine(invoice_id=invoice.pk, actor=request.user, **serializer.validated_data)
        return success_response(self._detail(invoice.pk), message="Fine added.", status=201)

    @action(detail=True, methods=["post"], url_path="payments")
    def add_payment(self, request, pk=None):
        invoice = self.get_object()
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = FeeService.record_payment(invoice_id=invoice.pk, actor=request.user, request=request, **serializer.validated_data)
        return success_response({"payment": PaymentOut(payment).data, "invoice": self._detail(invoice.pk)}, message="Payment recorded.", status=201)


class FeePaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    queryset = FeePayment.objects.select_related("invoice__student", "received_by")
    serializer_class = FeePaymentListSerializer
    lookup_value_regex = "[0-9a-fA-F-]{36}"
    permission_map = {"list": P.FEES_VIEW, "retrieve": P.FEES_VIEW, "reverse": P.FEES_REVERSE}

    def scope_queryset(self, queryset):
        return queryset.filter(invoice__student__in=visible_students(self.request.user, Student.objects.filter(school=self.request.user.school)))

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != "list":
            return queryset
        params = self.request.query_params
        try:
            for param, lookup in {"invoice": "invoice_id", "student": "invoice__student_id", "method": "method", "status": "status"}.items():
                if params.get(param):
                    queryset = queryset.filter(**{lookup: params[param].strip()})
            if params.get("date_from"):
                queryset = queryset.filter(paid_on__gte=params["date_from"])
            if params.get("date_to"):
                queryset = queryset.filter(paid_on__lte=params["date_to"])
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"detail": ["Invalid filter value."]}) from exc
        return queryset.order_by("-paid_on", "-receipt_number")

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        payment = self.get_object()
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        FeeService.reverse_payment(payment_id=payment.pk, reason=serializer.validated_data["reason"], actor=request.user, request=request)
        return success_response(FeePaymentListSerializer(self.get_queryset().get(pk=payment.pk)).data, message="Payment reversed.")
