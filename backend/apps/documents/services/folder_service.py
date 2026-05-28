import logging
from typing import TYPE_CHECKING

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError
from apps.documents.models import Document, Folder

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


def create_folder(
    organization: "Organization",
    owner: "User",
    name: str,
    parent: Folder | None = None,
) -> Folder:
    """Create a folder. Validates that parent belongs to the same organization."""
    if parent is not None and parent.organization_id != organization.pk:
        raise PermissionDenied("Parent folder does not belong to this organization.")

    folder = Folder.objects.create(
        organization=organization,
        name=name,
        parent=parent,
        owner=owner,
    )
    audit_service.log(
        organization=organization,
        user=owner,
        entity_type="folder",
        entity_id=str(folder.id),
        action=AuditAction.CREATE,
        new_values={"name": name, "parent_id": str(parent.id) if parent else None},
    )
    logger.info("Folder created: %s (org=%s)", folder.id, organization.id)
    return folder


def rename_folder(
    organization: "Organization",
    user: "User",
    folder: Folder,
    new_name: str,
) -> Folder:
    """Rename a folder and record an audit trail."""
    old_name = folder.name
    folder.name = new_name
    folder.save(update_fields=["name", "updated_at"])
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="folder",
        entity_id=str(folder.id),
        action=AuditAction.UPDATE,
        old_values={"name": old_name},
        new_values={"name": new_name},
    )
    return folder


def move_folder(
    organization: "Organization",
    user: "User",
    folder: Folder,
    new_parent: Folder | None,
) -> Folder:
    """
    Move a folder to a new parent. Validates org ownership and detects cycles.
    new_parent=None moves the folder to the root level.
    """
    if new_parent is not None:
        if new_parent.organization_id != organization.pk:
            raise PermissionDenied(
                "Target parent does not belong to this organization."
            )
        _assert_no_cycle(folder, new_parent)

    old_parent_id = str(folder.parent_id) if folder.parent_id else None
    folder.parent = new_parent
    folder.save(update_fields=["parent", "updated_at"])
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="folder",
        entity_id=str(folder.id),
        action=AuditAction.UPDATE,
        old_values={"parent_id": old_parent_id},
        new_values={"parent_id": str(new_parent.id) if new_parent else None},
    )
    return folder


def soft_delete_folder(
    organization: "Organization",
    user: "User",
    folder: Folder,
) -> None:
    """
    Soft-delete a folder. Refuses if it has live children or live documents.
    Cascade physical deletion is deferred to a Celery housekeeping task (Phase 4).
    """
    has_children = Folder.objects.filter(
        organization=organization, parent=folder
    ).exists()
    if has_children:
        raise ConflictError("Cannot delete a folder that has sub-folders.")

    has_documents = Document.objects.filter(
        organization=organization, folder=folder
    ).exists()
    if has_documents:
        raise ConflictError("Cannot delete a folder that contains documents.")

    folder.soft_delete()
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="folder",
        entity_id=str(folder.id),
        action=AuditAction.DELETE,
        old_values={"name": folder.name},
    )
    logger.info("Folder soft-deleted: %s (org=%s)", folder.id, organization.id)


def _assert_no_cycle(folder: Folder, new_parent: Folder) -> None:
    """Walk up the ancestry of new_parent to ensure folder is not already there."""
    current = new_parent
    while current is not None:
        if current.pk == folder.pk:
            raise ValidationError(
                message="Moving this folder would create a cycle.",
                code="FOLDER_CYCLE",
            )
        current = current.parent
