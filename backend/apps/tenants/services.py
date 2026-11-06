import secrets
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService
from apps.core.exceptions import Conflict, DomainError
from apps.notifications.models import NotificationType, Severity
from apps.notifications.services import NotificationService
from apps.subscriptions.services import SubscriptionService

from .images import ImageService
from .models import School, SchoolSettings, SchoolStatus


class SchoolService:
    @staticmethod
    def create_school(*, name: str, **fields) -> School:
        base = slugify(name)[:60] or "school"
        for attempt in range(6):
            slug = base if attempt == 0 else f"{base}-{secrets.token_hex(3)}"
            try:
                with transaction.atomic():  # savepoint, so a slug collision does not poison the outer transaction
                    return School.objects.create(name=name, slug=slug, **fields)
            except IntegrityError:
                continue
        raise DomainError("Could not allocate a unique school identifier. Please try again.")

    @staticmethod
    @transaction.atomic
    def update_profile(*, school: School, actor, data: dict, request) -> School:
        data = dict(data)
        logo_changed = "logo" in data
        logo_value = data.pop("logo", None)
        changed = {field: value for field, value in data.items() if getattr(school, field) != value}
        if logo_changed:
            school.logo = ImageService.replace(school, school.logo, logo_value, kind="logo")
            changed["logo"] = bool(logo_value)
        if not changed:
            return school
        for field, value in changed.items():
            if field != "logo":
                setattr(school, field, value)
        school.save(update_fields=[*changed.keys(), "updated_at"])
        AuditService.record(
            AuditAction.SCHOOL_PROFILE_UPDATED, actor=actor, school=school, entity_type="school",
            entity_id=school.id, description="School profile updated", metadata={"fields": sorted(changed)},
            request=request,
        )
        return school


class SchoolOnboardingService:
    """Phase 2 registration: school + settings + School Admin (atomic).
    Phase 4 adds the trial subscription; later phases add default academic configuration. They hook in here."""

    @staticmethod
    def register(*, school_name, admin_name, email, phone, password, country, city, request=None):
        first, _, last = admin_name.strip().partition(" ")
        try:
            with transaction.atomic():
                school = SchoolService.create_school(
                    name=school_name, email=email, phone=phone, country=country, city=city
                )
                SchoolSettings.objects.create(school=school)
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first,
                    last_name=last.strip(),
                    phone=phone,
                    role=Role.SCHOOL_ADMIN,
                    school=school,
                )
                from .defaults import bootstrap_school

                bootstrap_school(school)
                SubscriptionService.start_trial(school, actor=user)  # duration/plan come from platform settings
                AuditService.record(
                    AuditAction.SCHOOL_REGISTERED, actor=user, school=school, entity_type="school",
                    entity_id=school.id, description=f"School '{school.name}' registered", request=request,
                )
        except IntegrityError as exc:  # concurrent registration with the same email
            raise ValidationError({"email": ["An account with this email already exists."]}) from exc
        from django.conf import settings as django_settings
        from apps.notifications.email import send_template

        send_template("welcome", user.email, {"name": user.first_name, "school": school.name, "url": f"{django_settings.FRONTEND_ORIGIN}/login"}, school=school)
        return school, user


@dataclass(frozen=True)
class Transition:
    allowed_from: frozenset
    to: str
    audit_action: str
    past_tense: str


TRANSITIONS = {
    "suspend": Transition(frozenset({SchoolStatus.ACTIVE}), SchoolStatus.SUSPENDED, AuditAction.SCHOOL_SUSPENDED, "suspended"),
    "deactivate": Transition(
        frozenset({SchoolStatus.ACTIVE, SchoolStatus.SUSPENDED}), SchoolStatus.INACTIVE,
        AuditAction.SCHOOL_DEACTIVATED, "deactivated",
    ),
    "reactivate": Transition(
        frozenset({SchoolStatus.SUSPENDED, SchoolStatus.INACTIVE}), SchoolStatus.ACTIVE,
        AuditAction.SCHOOL_REACTIVATED, "reactivated",
    ),
}

NOTICES = {
    "suspend": (NotificationType.SCHOOL_SUSPENDED, Severity.CRITICAL, "Your school account has been suspended"),
    "deactivate": (NotificationType.SCHOOL_DEACTIVATED, Severity.CRITICAL, "Your school account has been deactivated"),
    "reactivate": (NotificationType.SCHOOL_REACTIVATED, Severity.INFO, "Your school account is active again"),
}


class SchoolLifecycleService:
    """Super Admin controls over school access. Nothing is ever deleted: only `school.status` changes,
    and the tenant gate (TenantAccess) turns that into a 403 for the school's users.
    This status is independent of the subscription status added in Phase 4."""

    @staticmethod
    def change_status(*, school: School, action: str, actor, reason: str, request) -> None:
        transition = TRANSITIONS[action]
        now = timezone.now()
        with transaction.atomic():
            # Conditional UPDATE: two concurrent admins cannot both apply a transition.
            updated = School.objects.filter(pk=school.pk, status__in=transition.allowed_from).update(
                status=transition.to,
                status_reason=reason if transition.to != SchoolStatus.ACTIVE else "",
                status_changed_at=now,
                status_changed_by=actor,
                updated_at=now,
            )
            if updated == 0:
                current = School.objects.values_list("status", flat=True).get(pk=school.pk)
                raise Conflict(
                    f"This school is {current.lower()} and cannot be {transition.past_tense}.",
                    code="invalid_transition",
                )
            AuditService.record(
                transition.audit_action, actor=actor, school=school, entity_type="school", entity_id=school.id,
                description=f"School {transition.past_tense}" + (f": {reason}" if reason else ""),
                metadata={"to": transition.to, "reason": reason}, request=request,
            )
            notice_type, severity, title = NOTICES[action]
            NotificationService.notify_school_admins(
                school, type=notice_type, severity=severity, title=title,
                body=reason or "You can use the application again.",
            )
