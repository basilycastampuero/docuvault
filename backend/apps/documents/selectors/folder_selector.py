import uuid
from typing import TYPE_CHECKING

from apps.core.exceptions import NotFound
from apps.documents.models import Folder

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.organizations.models import Organization


def get_folder_by_id(
    organization: "Organization", folder_id: str | uuid.UUID
) -> Folder:
    """Return a folder by id, scoped to the organization. Raises NotFound otherwise."""
    try:
        return Folder.objects.select_related("owner", "parent").get(
            id=folder_id, organization=organization
        )
    except Folder.DoesNotExist:
        raise NotFound(f"Folder {folder_id} not found.")


def get_root_folders(organization: "Organization") -> "QuerySet[Folder]":
    """Return all top-level (parentless) folders for an organization."""
    return (
        Folder.objects.filter(organization=organization, parent__isnull=True)
        .select_related("owner")
        .order_by("name")
    )


def get_children(organization: "Organization", folder: Folder) -> "QuerySet[Folder]":
    """Return direct children of a folder, scoped to the organization."""
    return (
        Folder.objects.filter(organization=organization, parent=folder)
        .select_related("owner")
        .order_by("name")
    )


def get_folder_tree(organization: "Organization") -> "QuerySet[Folder]":
    """
    Return a flat, ordered queryset of all folders for the org, suitable for
    client-side tree construction. Serialise with FolderSerializer to get
    each folder's parent UUID alongside created_at/updated_at.
    """
    return (
        Folder.objects.filter(organization=organization)
        .select_related("owner")
        .order_by("name")
    )
