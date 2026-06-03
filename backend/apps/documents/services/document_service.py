import logging
from typing import IO, TYPE_CHECKING

from django.conf import settings
from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.core.exceptions import (
    AIServiceUnavailableError,
    ConflictError,
    PermissionDenied,
)
from apps.documents.models import Document, DocumentStatus, DocumentVersion, Folder
from apps.documents.storage import StorageService, validate_file
from apps.documents.tasks.document_tasks import process_ocr

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization

logger = logging.getLogger(__name__)

_MANUAL_STATUS_TRANSITIONS = {
    DocumentStatus.DRAFT: {DocumentStatus.UNDER_REVIEW},
    DocumentStatus.UNDER_REVIEW: {DocumentStatus.DRAFT},
}


@transaction.atomic
def create_document(
    organization: "Organization",
    user: "User",
    file: IO[bytes],
    name: str,
    folder: Folder | None = None,
    description: str = "",
    tags: list[str] | None = None,
) -> Document:
    """Upload a file and create a Document with its initial DocumentVersion."""
    if folder is not None and folder.organization_id != organization.pk:
        raise PermissionDenied("Folder does not belong to this organization.")

    mime_type, file_size, checksum = validate_file(file)

    doc = Document.objects.create(
        organization=organization,
        folder=folder,
        name=name,
        description=description,
        mime_type=mime_type,
        file_size=file_size,
        checksum=checksum,
        storage_path="",
        status=DocumentStatus.DRAFT,
        version=1,
        created_by=user,
        tags=tags or [],
    )

    storage = StorageService()
    path = StorageService.build_storage_path(str(organization.id), str(doc.id), name)
    storage.upload_file(file, path, content_type=mime_type)
    doc.storage_path = path
    doc.save(update_fields=["storage_path", "updated_at"])

    DocumentVersion.objects.create(
        document=doc,
        version_number=1,
        storage_path=path,
        file_size=file_size,
        checksum=checksum,
        mime_type=mime_type,
        created_by=user,
        change_description="Initial version",
    )

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(doc.id),
        action=AuditAction.CREATE,
        new_values={"name": name, "mime_type": mime_type, "file_size": file_size},
    )

    transaction.on_commit(lambda: process_ocr.delay(str(doc.id)))
    logger.info("Document created: %s (org=%s)", doc.id, organization.id)
    return doc


@transaction.atomic
def upload_new_version(
    organization: "Organization",
    user: "User",
    document: Document,
    file: IO[bytes],
    change_description: str = "",
) -> Document:
    """Upload a new file version, incrementing the document's version counter."""
    mime_type, file_size, checksum = validate_file(file)

    new_version_number = document.version + 1
    path = StorageService.build_storage_path(
        str(organization.id), str(document.id), f"v{new_version_number}_{document.name}"
    )

    storage = StorageService()
    storage.upload_file(file, path, content_type=mime_type)

    DocumentVersion.objects.create(
        document=document,
        version_number=new_version_number,
        storage_path=path,
        file_size=file_size,
        checksum=checksum,
        mime_type=mime_type,
        created_by=user,
        change_description=change_description,
    )

    old_version = document.version
    document.storage_path = path
    document.version = new_version_number
    document.mime_type = mime_type
    document.file_size = file_size
    document.checksum = checksum
    document.save(
        update_fields=[
            "storage_path",
            "version",
            "mime_type",
            "file_size",
            "checksum",
            "updated_at",
        ]
    )

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(document.id),
        action=AuditAction.UPDATE,
        old_values={"version": old_version},
        new_values={"version": new_version_number, "file_size": file_size},
    )
    return document


@transaction.atomic
def update_document_metadata(
    organization: "Organization",
    user: "User",
    document: Document,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> Document:
    """Update mutable metadata fields: name, description, tags."""
    update_fields = ["updated_at"]
    old_values: dict = {}
    new_values: dict = {}

    if name is not None:
        old_values["name"] = document.name
        document.name = name
        new_values["name"] = name
        update_fields.append("name")

    if description is not None:
        old_values["description"] = document.description
        document.description = description
        new_values["description"] = description
        update_fields.append("description")

    if tags is not None:
        old_values["tags"] = document.tags
        document.tags = tags
        new_values["tags"] = tags
        update_fields.append("tags")

    if len(update_fields) > 1:
        document.save(update_fields=update_fields)
        audit_service.log(
            organization=organization,
            user=user,
            entity_type="document",
            entity_id=str(document.id),
            action=AuditAction.UPDATE,
            old_values=old_values,
            new_values=new_values,
        )
    return document


@transaction.atomic
def change_document_status(
    organization: "Organization",
    user: "User",
    document: Document,
    new_status: DocumentStatus,
) -> Document:
    """
    Transition document status. Phase 2 only allows draft ↔ under_review.
    approved/rejected require WorkflowExecution (Phase 3.2).
    """
    current = DocumentStatus(document.status)
    allowed_next = _MANUAL_STATUS_TRANSITIONS.get(current, set())

    if new_status not in allowed_next:
        raise ConflictError(
            message=(
                f"Cannot transition from '{current}' to '{new_status}' manually. "
                "Transitions to approved/rejected require a workflow execution."
            ),
            code="INVALID_STATUS_TRANSITION",
        )

    old_status = document.status
    document.status = new_status
    document.save(update_fields=["status", "updated_at"])

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(document.id),
        action=AuditAction.STATUS_CHANGE,
        old_values={"status": old_status},
        new_values={"status": new_status},
    )
    return document


@transaction.atomic
def reprocess_ocr(
    organization: "Organization",
    user: "User",
    document: Document,
) -> Document:
    """Re-trigger the OCR pipeline for a document. The task is dispatched after
    commit so the worker never picks it up before this transaction is durable."""
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(document.id),
        action=AuditAction.UPDATE,
        metadata={"via": "ocr_reprocess"},
    )
    transaction.on_commit(lambda: process_ocr.delay(str(document.id)))
    logger.info("OCR reprocess requested: %s (org=%s)", document.id, organization.id)
    return document


def request_ai_analysis(
    organization: "Organization",
    user: "User",
    document: Document,
) -> Document:
    """Validate and enqueue AI analysis for a document. Returns the document unchanged.

    Fails fast (in the request) if the feature is disabled or the document has
    no OCR content — better than silently failing inside the worker.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIServiceUnavailableError()

    if not (document.ocr_content or "").strip():
        raise ConflictError(
            "Document has no OCR content to analyze", code="AI_NO_CONTENT"
        )

    # Lazy import avoids circular dependency between document_service and tasks.
    from apps.documents.tasks.document_tasks import analyze_document

    transaction.on_commit(lambda: analyze_document.delay(str(document.id)))
    logger.info("AI analysis enqueued: %s (org=%s)", document.id, organization.id)
    return document


@transaction.atomic
def soft_delete_document(
    organization: "Organization",
    user: "User",
    document: Document,
) -> None:
    """
    Soft-delete a document. The file is NOT removed from storage here;
    housekeeping (orphan blob cleanup) is deferred to Phase 4.
    """
    document.soft_delete()
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(document.id),
        action=AuditAction.DELETE,
        old_values={"name": document.name, "status": document.status},
    )
    logger.info("Document soft-deleted: %s (org=%s)", document.id, organization.id)
