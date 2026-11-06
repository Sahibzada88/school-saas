import uuid

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.roles import P, Role
from apps.accounts.serializers import SchoolUserSerializer
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.models import AuditLog
from apps.audit_logs.serializers import PlatformAuditLogSerializer
from apps.audit_logs.services import AuditService
from apps.core.exceptions import DomainError
from apps.core.responses import success_response
from apps.core.viewsets import PlatformAPIView, PlatformViewSet
from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService
from apps.payments.models import PaymentMethod, PlatformPayment
from apps.payments.services import PaymentService
from apps.subscriptions.models import Plan, SubscriptionStatus
from apps.subscriptions.services import SubscriptionService
from apps.subscriptions.state import expiring_filter
from apps.tenants.models import SchoolStatus
from apps.tenants.services import TRANSITIONS, SchoolLifecycleService

from .config import PlatformConfig, describe_settings, update_settings
from .selectors import annotated_schools, annotated_subscriptions
from .serializers import (
    ChangePlanSerializer,
    DaysReasonSerializer,
    LifecycleSerializer,
    NotifySerializer,
    PaymentSerializer,
    PlanSerializer,
    PlatformSchoolDetailSerializer,
    PlatformSchoolListSerializer,
    PlatformSubscriptionSerializer,
    ReasonConfirmSerializer,
    ReasonSerializer,
    RecordPaymentSerializer,
)
from .services import build_platform_dashboard, create_plan, update_plan

UUID_REGEX = "[0-9a-fA-F-]{36}"
SCHOOL_ORDERING = {"name", "created_at", "status", "user_count"}
SUBSCRIPTION_STATES = {*SubscriptionStatus.values, "NONE"}


def _parse_uuid(value: str, field: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise ValidationError({field: ["Invalid id."]}) from exc


def _parse_date(value: str, field: str):
    try:
        parsed = parse_date(value)
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValidationError({field: ["Use YYYY-MM-DD."]})
    return parsed


class _BillingContextMixin:
    """Loads the platform config once per request for serializers that compute the effective subscription state."""

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not hasattr(self, "_billing_context"):  # one settings query per request, one consistent "now"
            self._billing_context = (PlatformConfig.load(), timezone.now())
        context["cfg"], context["now"] = self._billing_context
        return context


class PlatformDashboardView(PlatformAPIView):
    required_permission = P.PLATFORM_DASHBOARD

    def get(self, request):
        return success_response(build_platform_dashboard(), message="")


# ===================================================================== schools
class PlatformSchoolViewSet(_BillingContextMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, PlatformViewSet):
    """/api/v1/platform/schools/ : cross-school management. Tenant data tabs are read-only and audited."""

    lookup_value_regex = UUID_REGEX
    permission_map = {
        "list": P.PLATFORM_SCHOOLS,
        "retrieve": P.PLATFORM_SCHOOLS,
        "suspend": P.PLATFORM_SCHOOLS,
        "deactivate": P.PLATFORM_SCHOOLS,
        "reactivate": P.PLATFORM_SCHOOLS,
        "notify": P.PLATFORM_SCHOOLS,
        "users": P.PLATFORM_TENANT_DATA,
        "activity": P.PLATFORM_TENANT_DATA,
    }

    def get_serializer_class(self):
        return PlatformSchoolListSerializer if self.action == "list" else PlatformSchoolDetailSerializer

    def get_queryset(self):
        context = self.get_serializer_context()
        qs = annotated_schools(context["now"], context["cfg"])
        if self.action != "list":
            return qs
        params = self.request.query_params
        status = params.get("status", "").strip()
        if status:
            if status not in SchoolStatus.values:
                raise ValidationError({"status": ["Invalid status."]})
            qs = qs.filter(status=status)
        state = params.get("subscription_state", "").strip()
        if state:
            if state not in SUBSCRIPTION_STATES:
                raise ValidationError({"subscription_state": ["Invalid subscription state."]})
            qs = qs.filter(subscription_state=state)
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(slug__icontains=search) | Q(email__icontains=search) | Q(city__icontains=search)
            )
        ordering = params.get("ordering", "-created_at")
        if ordering.lstrip("-") not in SCHOOL_ORDERING:
            ordering = "-created_at"
        return qs.order_by(ordering, "name")

    # ------------------------------------------------------------------ read-only tenant tabs
    @action(detail=True, methods=["get"], url_path="users")
    def users(self, request, pk=None):
        school = self.get_object()
        AuditService.record(
            AuditAction.PLATFORM_VIEWED_SCHOOL_USERS, actor=request.user, school=school, entity_type="school",
            entity_id=school.id, description=f"Viewed the user list of {school.name}", request=request,
        )
        queryset = User.objects.filter(school=school).order_by("first_name", "last_name", "email")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(SchoolUserSerializer(page, many=True).data)

    @action(detail=True, methods=["get"], url_path="activity")
    def activity(self, request, pk=None):
        school = self.get_object()
        queryset = AuditLog.objects.filter(school=school).select_related("actor", "school").order_by("-created_at")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(PlatformAuditLogSerializer(page, many=True).data)

    # ------------------------------------------------------------------ lifecycle
    def _transition(self, request, action_name: str, require_reason: bool):
        school = self.get_object()
        serializer = LifecycleSerializer(data=request.data, context={"require_reason": require_reason})
        serializer.is_valid(raise_exception=True)
        SchoolLifecycleService.change_status(
            school=school, action=action_name, actor=request.user,
            reason=serializer.validated_data["reason"], request=request,
        )
        fresh = self.get_queryset().get(pk=school.pk)
        return success_response(
            PlatformSchoolDetailSerializer(fresh, context=self.get_serializer_context()).data,
            message=f"School {TRANSITIONS[action_name].past_tense}.",
        )

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        return self._transition(request, "suspend", require_reason=True)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return self._transition(request, "deactivate", require_reason=True)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        return self._transition(request, "reactivate", require_reason=False)

    # ------------------------------------------------------------------ notify
    @action(detail=True, methods=["post"])
    def notify(self, request, pk=None):
        school = self.get_object()
        serializer = NotifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            recipients = NotificationService.notify_school_admins(
                school, type=NotificationType.ANNOUNCEMENT, title=data["title"], body=data["body"], severity=data["severity"]
            )
            if recipients == 0:
                raise DomainError("This school has no active School Admin to notify.", code="no_recipients")
            AuditService.record(
                AuditAction.PLATFORM_NOTIFICATION_SENT, actor=request.user, school=school, entity_type="school",
                entity_id=school.id, description=f"Sent notification: {data['title']}", request=request,
            )
        return success_response({"recipients": recipients}, message="Notification sent.")


# ===================================================================== plans
class PlatformPlanViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, PlatformViewSet
):
    """/api/v1/platform/plans/ : plans are data. No DELETE: retire a plan with is_active=false."""

    serializer_class = PlanSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    lookup_value_regex = UUID_REGEX
    pagination_class = None  # a handful of plans; the UI shows them all
    permission_map = {
        "list": P.PLATFORM_PLANS, "retrieve": P.PLATFORM_PLANS, "create": P.PLATFORM_PLANS, "partial_update": P.PLATFORM_PLANS,
    }

    def get_queryset(self):
        return Plan.objects.annotate(subscriber_count=Count("subscriptions")).order_by("sort_order", "name")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = create_plan(serializer=serializer, actor=request.user, request=request)
        return success_response(PlanSerializer(self.get_queryset().get(pk=plan.pk)).data, message="Plan created.", status=201)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            raise ValidationError({"non_field_errors": ["No changes provided."]})
        plan = update_plan(serializer=serializer, actor=request.user, request=request)
        return success_response(PlanSerializer(self.get_queryset().get(pk=plan.pk)).data, message="Plan updated.")


# ===================================================================== subscriptions
SUBSCRIPTION_ORDERING = {
    "school": ("school__name",), "-school": ("-school__name",),
    "ends_at": (F("ends_at").asc(nulls_last=True),), "-ends_at": (F("ends_at").desc(nulls_last=True),),
    "created_at": ("created_at",), "-created_at": ("-created_at",),
}


class PlatformSubscriptionViewSet(_BillingContextMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, PlatformViewSet):
    """/api/v1/platform/subscriptions/ : every school's subscription with its computed (effective) state."""

    serializer_class = PlatformSubscriptionSerializer
    lookup_value_regex = UUID_REGEX
    permission_map = {
        "list": P.PLATFORM_SUBSCRIPTIONS, "retrieve": P.PLATFORM_SUBSCRIPTIONS, "extend_trial": P.PLATFORM_SUBSCRIPTIONS,
        "extend": P.PLATFORM_SUBSCRIPTIONS, "change_plan": P.PLATFORM_SUBSCRIPTIONS, "cancel": P.PLATFORM_SUBSCRIPTIONS,
        "suspend": P.PLATFORM_SUBSCRIPTIONS, "resume": P.PLATFORM_SUBSCRIPTIONS, "events": P.PLATFORM_SUBSCRIPTIONS,
    }

    def get_queryset(self):
        context = self.get_serializer_context()
        now, cfg = context["now"], context["cfg"]
        qs = annotated_subscriptions(now, cfg)
        if self.action != "list":
            return qs
        params = self.request.query_params
        state = params.get("state", "").strip()
        if state:
            if state not in SubscriptionStatus.values:
                raise ValidationError({"state": ["Invalid state."]})
            qs = qs.filter(effective=state)
        if params.get("plan"):
            qs = qs.filter(plan__slug=params["plan"].strip())
        if params.get("expiring") == "true":
            qs = qs.filter(expiring_filter(now, cfg))
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(school__name__icontains=search) | Q(school__slug__icontains=search))
        return qs.order_by(*SUBSCRIPTION_ORDERING.get(params.get("ordering", ""), ("-created_at",)), "school__name")

    def _respond(self, sub, message: str):
        fresh = self.get_queryset().get(pk=sub.pk)
        return success_response(PlatformSubscriptionSerializer(fresh, context=self.get_serializer_context()).data, message=message)

    @action(detail=True, methods=["post"], url_path="extend-trial")
    def extend_trial(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(DaysReasonSerializer, request)
        SubscriptionService.extend_trial(
            subscription_id=sub.pk, days=data["days"], actor=request.user, reason=data["reason"], request=request
        )
        return self._respond(sub, "Trial extended.")

    @action(detail=True, methods=["post"])
    def extend(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(DaysReasonSerializer, request)
        SubscriptionService.extend_subscription(
            subscription_id=sub.pk, days=data["days"], actor=request.user, reason=data["reason"], request=request
        )
        return self._respond(sub, "Subscription extended.")

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(ChangePlanSerializer, request)
        SubscriptionService.change_plan(
            subscription_id=sub.pk, plan=data["plan"], actor=request.user, reason=data["reason"], request=request
        )
        return self._respond(sub, "Plan changed.")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(ReasonConfirmSerializer, request)
        SubscriptionService.cancel(subscription_id=sub.pk, actor=request.user, reason=data["reason"], request=request)
        return self._respond(sub, "Subscription cancelled.")

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(ReasonConfirmSerializer, request)
        SubscriptionService.suspend(subscription_id=sub.pk, actor=request.user, reason=data["reason"], request=request)
        return self._respond(sub, "Subscription suspended.")

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        sub = self.get_object()
        data = self._valid(ReasonSerializer, request)
        SubscriptionService.resume(subscription_id=sub.pk, actor=request.user, reason=data["reason"], request=request)
        return self._respond(sub, "Subscription resumed.")

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        sub = self.get_object()
        rows = sub.events.select_related("actor", "from_plan", "to_plan").order_by("-created_at")[:100]
        data = [
            {
                "id": str(e.id), "created_at": e.created_at, "event_type": e.event_type, "from_status": e.from_status,
                "to_status": e.to_status, "delta_days": e.delta_days, "reason": e.reason,
                "from_plan": e.from_plan.name if e.from_plan_id else None, "to_plan": e.to_plan.name if e.to_plan_id else None,
                "actor_name": e.actor.full_name if e.actor_id else "System",
            }
            for e in rows
        ]
        return success_response(data, message="")

    @staticmethod
    def _valid(serializer_class, request) -> dict:
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


# ===================================================================== payments
class PlatformPaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, PlatformViewSet
):
    """/api/v1/platform/payments/ : SaaS subscription payments (manual). Append-only: no update, no delete."""

    serializer_class = PaymentSerializer
    lookup_value_regex = UUID_REGEX
    permission_map = {"list": P.PLATFORM_PAYMENTS, "retrieve": P.PLATFORM_PAYMENTS, "create": P.PLATFORM_PAYMENTS}

    def get_queryset(self):
        qs = PlatformPayment.objects.select_related("school", "created_by").order_by("-payment_date", "-created_at")
        params = self.request.query_params
        if params.get("school"):
            qs = qs.filter(school_id=_parse_uuid(params["school"].strip(), "school"))
        method = params.get("method", "").strip()
        if method:
            if method not in PaymentMethod.values:
                raise ValidationError({"method": ["Invalid payment method."]})
            qs = qs.filter(payment_method=method)
        if params.get("date_from"):
            qs = qs.filter(payment_date__gte=_parse_date(params["date_from"].strip(), "date_from"))
        if params.get("date_to"):
            qs = qs.filter(payment_date__lte=_parse_date(params["date_to"].strip(), "date_to"))
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(transaction_reference__icontains=search) | Q(school__name__icontains=search))
        return qs

    def create(self, request, *args, **kwargs):
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = PaymentService.record_payment(actor=request.user, request=request, **serializer.validated_data)
        return success_response(PaymentSerializer(payment).data, message="Payment recorded.", status=201)


# ===================================================================== settings
class PlatformSettingsView(PlatformAPIView):
    required_permission = P.PLATFORM_SETTINGS

    def get(self, request):
        return success_response(describe_settings(PlatformConfig.load()), message="")

    def patch(self, request):
        if not isinstance(request.data, dict) or not request.data:
            raise ValidationError({"non_field_errors": ["Send an object of setting values."]})
        config = update_settings(values=request.data, actor=request.user, request=request)
        return success_response(describe_settings(config), message="Settings saved.")


# ===================================================================== audit logs
class PlatformAuditLogViewSet(mixins.ListModelMixin, PlatformViewSet):
    """/api/v1/platform/audit-logs/ : platform-wide audit trail with filters."""

    queryset = AuditLog.objects.select_related("actor", "school").order_by("-created_at")
    serializer_class = PlatformAuditLogSerializer
    permission_map = {"list": P.PLATFORM_AUDIT, "action_names": P.PLATFORM_AUDIT}

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("action"):
            qs = qs.filter(action=params["action"].strip())
        if params.get("actor_role"):
            qs = qs.filter(actor_role=params["actor_role"].strip())
        if params.get("school"):
            qs = qs.filter(school_id=_parse_uuid(params["school"].strip(), "school"))
        if params.get("date_from"):
            qs = qs.filter(created_at__date__gte=_parse_date(params["date_from"].strip(), "date_from"))
        if params.get("date_to"):
            qs = qs.filter(created_at__date__lte=_parse_date(params["date_to"].strip(), "date_to"))
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(description__icontains=search) | Q(actor__email__icontains=search))
        return qs

    @action(detail=False, methods=["get"], url_path="actions", url_name="actions", pagination_class=None)
    def action_names(self, request):
        return success_response(AuditAction.all(), message="")
