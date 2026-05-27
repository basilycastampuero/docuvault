from django.db.models import QuerySet

from apps.core.exceptions import NotFound
from apps.organizations.models import Organization


def get_by_id(organization_id: str) -> Organization:
    """Return an organization by its UUID. Raises NotFound if it does not exist."""
    try:
        return Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        raise NotFound(message=f"Organization '{organization_id}' not found")


def get_by_slug(slug: str) -> Organization:
    """Return an organization by its slug. Raises NotFound if it does not exist."""
    try:
        return Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        raise NotFound(message=f"Organization '{slug}' not found")


def get_all_active() -> QuerySet:
    """Return all active, non-deleted organizations."""
    return Organization.objects.filter(is_active=True)
