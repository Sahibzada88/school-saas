"""Typed platform settings with defaults. Rows in PlatformSetting override the defaults; an invalid or missing row
silently falls back to the default so a bad value can never take the platform down."""
from dataclasses import dataclass, fields
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit_logs.actions import AuditAction
from apps.audit_logs.services import AuditService

from .models import PlatformSetting


@dataclass(frozen=True)
class SettingSpec:
    key: str
    kind: str  # "int" | "choice" | "str"
    default: Any
    description: str
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] = ()
    max_length: int = 80


SPECS: dict[str, SettingSpec] = {
    spec.key: spec
    for spec in (
        SettingSpec("trial_duration_days", "int", 7, "Length of the free trial for new schools (days).", 1, 90),
        SettingSpec("trial_expiring_notice_days", "int", 2, "Warn trial schools this many days before the trial ends.", 1, 30),
        SettingSpec("expiring_notice_days", "int", 7, "Warn paid schools this many days before the subscription ends.", 1, 60),
        SettingSpec("past_due_grace_days", "int", 5, "Full access continues this many days after a subscription ends.", 0, 60),
        SettingSpec(
            "expired_access_mode", "choice", "READ_ONLY",
            "READ_ONLY keeps viewing/exports working after expiry; BLOCKED locks the school out.",
            choices=("READ_ONLY", "BLOCKED"),
        ),
        SettingSpec("school_image_quota_mb", "int", 50, "Maximum total size of stored images per school (MB).", 1, 1000),
        SettingSpec("trial_plan_slug", "str", "", "Plan assigned to trial subscriptions (empty = no plan, no limits).", max_length=80),
    )
}


def validate_value(spec: SettingSpec, raw: Any) -> Any:
    if spec.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError("Must be a whole number.")
        if spec.minimum is not None and raw < spec.minimum:
            raise ValueError(f"Must be at least {spec.minimum}.")
        if spec.maximum is not None and raw > spec.maximum:
            raise ValueError(f"Must be at most {spec.maximum}.")
        return raw
    if spec.kind == "choice":
        if raw not in spec.choices:
            raise ValueError(f"Must be one of: {', '.join(spec.choices)}.")
        return raw
    if not isinstance(raw, str):
        raise ValueError("Must be text.")
    value = raw.strip()
    if len(value) > spec.max_length:
        raise ValueError(f"Must be at most {spec.max_length} characters.")
    return value


@dataclass(frozen=True)
class PlatformConfig:
    trial_duration_days: int = 7
    trial_expiring_notice_days: int = 2
    expiring_notice_days: int = 7
    past_due_grace_days: int = 5
    expired_access_mode: str = "READ_ONLY"
    trial_plan_slug: str = ""
    school_image_quota_mb: int = 50

    @classmethod
    def defaults(cls) -> "PlatformConfig":
        return cls()

    @classmethod
    def load(cls) -> "PlatformConfig":
        """One query. No in-process caching (serverless instances would serve stale values)."""
        stored = dict(PlatformSetting.objects.values_list("key", "value"))
        values = {}
        for spec in SPECS.values():
            try:
                values[spec.key] = validate_value(spec, stored.get(spec.key, spec.default))
            except ValueError:
                values[spec.key] = spec.default
        return cls(**values)

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def describe_settings(config: PlatformConfig) -> list[dict]:
    current = config.as_dict()
    return [
        {
            "key": spec.key, "kind": spec.kind, "value": current[spec.key], "default": spec.default,
            "description": spec.description, "minimum": spec.minimum, "maximum": spec.maximum,
            "choices": list(spec.choices), "max_length": spec.max_length if spec.kind == "str" else None,
        }
        for spec in SPECS.values()
    ]


@transaction.atomic
def update_settings(*, values: dict, actor, request) -> PlatformConfig:
    before = PlatformConfig.load().as_dict()
    errors, clean = {}, {}
    for key, raw in values.items():
        spec = SPECS.get(key)
        if spec is None:
            errors[key] = ["Unknown setting."]
            continue
        try:
            clean[key] = validate_value(spec, raw)
        except ValueError as exc:
            errors[key] = [str(exc)]
    if errors:
        raise ValidationError(errors)

    changed = {}
    for key, value in clean.items():
        if before[key] != value:
            PlatformSetting.objects.update_or_create(key=key, defaults={"value": value, "updated_by": actor})
            changed[key] = {"from": before[key], "to": value}
    if changed:
        AuditService.record(
            AuditAction.PLATFORM_SETTING_CHANGED, actor=actor, entity_type="platform_settings",
            description="Platform settings changed: " + ", ".join(sorted(changed)), metadata={"changes": changed},
            request=request,
        )
    return PlatformConfig.load()
