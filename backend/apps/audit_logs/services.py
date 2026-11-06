import logging

from apps.core.utils import get_client_ip

from .models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    def record(
        action: str,
        *,
        actor=None,
        school=None,
        entity_type: str = "",
        entity_id="",
        description: str = "",
        metadata: dict | None = None,
        request=None,
    ) -> AuditLog:
        """Write one audit row. Call inside the same transaction as the change it describes."""
        ip = getattr(request, "client_ip", None) or (get_client_ip(request) if request is not None else None)
        if school is None and actor is not None:
            school = getattr(actor, "school", None)
        return AuditLog.objects.create(
            actor=actor,
            actor_role=getattr(actor, "role", "") or "",
            school=school,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else "",
            description=description,
            metadata=metadata or {},
            ip=ip,
        )
