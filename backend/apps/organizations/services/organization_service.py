import logging

from django.utils.text import slugify

from apps.core.exceptions import ConflictError
from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


def create_organization(name: str, slug: str | None = None) -> Organization:
    """Create a new organization. Auto-generates slug from name if not provided."""
    final_slug = slug if slug else slugify(name)

    if Organization.objects.filter(slug=final_slug).exists():
        raise ConflictError(
            message=f"An organization with slug '{final_slug}' already exists",
            code="SLUG_TAKEN",
        )

    org = Organization.objects.create(name=name, slug=final_slug)
    logger.info("Organization created: %s (slug=%s)", org.id, org.slug)
    return org


def update_organization(
    organization: Organization,
    name: str | None = None,
    settings: dict | None = None,
) -> Organization:
    """Update mutable fields of an organization. Slug is immutable after creation."""
    update_fields = ["updated_at"]

    if name is not None:
        organization.name = name
        update_fields.append("name")

    if settings is not None:
        organization.settings = settings
        update_fields.append("settings")

    if len(update_fields) > 1:
        organization.save(update_fields=update_fields)

    return organization


def deactivate_organization(organization: Organization) -> Organization:
    """Mark organization as inactive. Does not delete it or its data."""
    organization.is_active = False
    organization.save(update_fields=["is_active", "updated_at"])
    logger.info("Organization deactivated: %s", organization.id)
    return organization
