import uuid
from typing import TYPE_CHECKING

from apps.core.exceptions import NotFound
from apps.documents.models import Document, DocumentStatus, DocumentVersion

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.organizations.models import Organization


def get_document_by_id(
    organization: "Organization", document_id: str | uuid.UUID
) -> Document:
    """Return a document by id scoped to the organization. Raises NotFound otherwise."""
    try:
        return Document.objects.select_related("folder", "created_by").get(
            id=document_id, organization=organization
        )
    except Document.DoesNotExist:
        raise NotFound(f"Document {document_id} not found.")


def get_documents(
    organization: "Organization",
    folder=None,
    status: DocumentStatus | None = None,
    tags: list[str] | None = None,
    search: str | None = None,
) -> "QuerySet[Document]":
    """Return a filtered queryset of documents for the organization."""
    qs = (
        Document.objects.filter(organization=organization)
        .select_related("folder", "created_by")
        .order_by("-created_at")
    )

    if folder is not None:
        qs = qs.filter(folder=folder)

    if status is not None:
        qs = qs.filter(status=status)

    if tags:
        qs = qs.filter(tags__overlap=tags)

    if search:
        qs = qs.filter(name__icontains=search)

    return qs


def get_document_versions(
    organization: "Organization", document: Document
) -> "QuerySet[DocumentVersion]":
    """Return all versions of a document, ordered newest first."""
    return (
        DocumentVersion.objects.filter(document=document)
        .select_related("created_by")
        .order_by("-version_number")
    )
