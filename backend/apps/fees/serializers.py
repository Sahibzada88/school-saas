from datetime import date

from rest_framework import serializers

from apps.academics.models import AcademicSession, Section, SchoolClass
from apps.core.fields import TenantScopedRelatedField

from .models import DiscountKind, FeeCategory, FeeMethod, FeePayment, FeeStructure, FeeStructureItem, Frequency, InvoiceStatus, StudentInvoice


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ("id", "name", "code", "is_recurring")
        read_only_fields = ("id",)

    def validate_code(self, value):
        return value.strip().upper()


class FeeStructureItemSerializer(serializers.ModelSerializer):
    category = TenantScopedRelatedField(queryset=FeeCategory.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = FeeStructureItem
        fields = ("category", "category_name", "amount")

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("The amount cannot be negative.")
        return value


class FeeStructureSerializer(serializers.ModelSerializer):
    session = TenantScopedRelatedField(queryset=AcademicSession.objects.all())
    school_class = TenantScopedRelatedField(queryset=SchoolClass.objects.all(), required=False, allow_null=True)
    items = FeeStructureItemSerializer(many=True, required=False)
    session_name = serializers.CharField(source="session.name", read_only=True)
    class_name = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = FeeStructure
        fields = ("id", "name", "session", "session_name", "school_class", "class_name", "frequency", "items", "total")
        read_only_fields = ("id", "session_name", "class_name", "total")

    def get_class_name(self, obj):
        return obj.school_class.name if obj.school_class_id else "All classes"

    def get_total(self, obj):
        return str(sum(i.amount for i in obj.items.all()))

    def validate_items(self, items):
        categories = [i["category"].id for i in items]
        if len(categories) != len(set(categories)):
            raise serializers.ValidationError("A fee category can only appear once per structure.")
        return items


class StudentBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    student_number = serializers.CharField()


class InvoiceListSerializer(serializers.ModelSerializer):
    student = StudentBriefSerializer(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = StudentInvoice
        fields = ("id", "invoice_number", "student", "period_label", "issue_date", "due_date", "total", "paid_total", "balance", "status", "is_overdue")
        read_only_fields = fields

    def get_is_overdue(self, obj):
        return obj.status in (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID) and obj.due_date < date.today()


class InvoiceItemOut(serializers.Serializer):
    description = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class DiscountOut(serializers.Serializer):
    kind = serializers.CharField()
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()


class FineOut(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()
    applied_on = serializers.DateField()


class PaymentOut(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = ("id", "receipt_number", "amount", "method", "reference", "paid_on", "status", "reversal_reason")
        read_only_fields = fields


class InvoiceDetailSerializer(InvoiceListSerializer):
    items = InvoiceItemOut(many=True, read_only=True)
    discounts = DiscountOut(many=True, read_only=True)
    fines = FineOut(many=True, read_only=True)
    payments = PaymentOut(many=True, read_only=True)
    session_name = serializers.CharField(source="session.name", read_only=True)
    guardian = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + ("subtotal", "discount_total", "fine_total", "void_reason", "session_name", "guardian", "items", "discounts", "fines", "payments")
        read_only_fields = fields

    def get_guardian(self, obj):
        link = obj.student.guardian_links.select_related("guardian").order_by("-is_primary", "created_at").first()
        return {"name": link.guardian.full_name, "phone": link.guardian.phone} if link else None


class GenerateInvoicesSerializer(serializers.Serializer):
    structure = TenantScopedRelatedField(queryset=FeeStructure.objects.all())
    period_label = serializers.CharField(max_length=40)
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField()
    section = TenantScopedRelatedField(queryset=Section.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):
        attrs.setdefault("issue_date", date.today())
        if attrs["due_date"] < attrs["issue_date"]:
            raise serializers.ValidationError({"due_date": ["The due date cannot be before the issue date."]})
        attrs["period_label"] = attrs["period_label"].strip()
        return attrs


class DiscountInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=DiscountKind.choices)
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(min_length=3, max_length=200)


class FineInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    reason = serializers.CharField(min_length=3, max_length=200)


class PaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    method = serializers.ChoiceField(choices=FeeMethod.choices)
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    paid_on = serializers.DateField(required=False)

    def validate(self, attrs):
        attrs.setdefault("paid_on", date.today())
        return attrs


class ReminderInputSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["overdue", "due_soon"], default="overdue")
    days = serializers.IntegerField(min_value=1, max_value=30, default=7)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=300)


class FeePaymentListSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    student_name = serializers.CharField(source="invoice.student.full_name", read_only=True)
    student_number = serializers.CharField(source="invoice.student.student_number", read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FeePayment
        fields = ("id", "receipt_number", "invoice", "invoice_number", "student_name", "student_number", "amount", "method", "reference", "paid_on", "status", "received_by_name", "created_at")
        read_only_fields = fields

    def get_received_by_name(self, obj):
        return obj.received_by.full_name if obj.received_by_id else None
