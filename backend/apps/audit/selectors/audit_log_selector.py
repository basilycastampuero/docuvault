from typing import TYPE_CHECKING

from apps.audit.models import AuditLog
from apps.core.exceptions import NotFound

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.organizations.models import Organization


def get_logs(organization: "Organization") -> "QuerySet[AuditLog]":
    """Return all audit logs for the organization, newest first."""
    return (
        AuditLog.objects.filter(organization=organization)
        .select_related("user")
        .order_by("-created_at")
    )


def get_log_by_id(organization: "Organization", log_id: int) -> AuditLog:
    """Return a single audit log scoped to the organization. Raises NotFound otherwise."""
    try:
        return AuditLog.objects.select_related("user").get(
            id=log_id, organization=organization
        )
    except AuditLog.DoesNotExist:
        raise NotFound(f"Audit log {log_id} not found.")
