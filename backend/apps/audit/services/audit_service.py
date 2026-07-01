import logging
from typing import TYPE_CHECKING

from apps.audit.models import AuditAction, AuditLog

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.authentication.models import User
    from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


def log(
    organization: "Organization",
    user: "User | None",
    entity_type: str,
    entity_id: str,
    action: AuditAction | str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    request: "HttpRequest | None" = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Record an immutable audit event. Always call from services, never from views."""
    ip_address = None
    user_agent = ""

    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (
            forwarded.split(",")[0].strip()
            if forwarded
            else request.META.get("REMOTE_ADDR")
        )
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

    entry = AuditLog(
        organization=organization,
        user=user,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        old_values=old_values or {},
        new_values=new_values or {},
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
    entry.save()
    logger.debug(
        "Audit: org=%s user=%s action=%s entity=%s:%s",
        organization.id,
        getattr(user, "id", None),
        action,
        entity_type,
        entity_id,
    )
    return entry
