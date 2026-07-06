import io
import logging
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError
from django.conf import settings
from pdf2image import convert_from_bytes
from PIL import Image

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.core.exceptions import TransientError
from apps.documents.models import ThumbnailStatus
from apps.documents.storage import StorageService

if TYPE_CHECKING:
    from apps.documents.models import Document

logger = logging.getLogger(__name__)

_IMAGE_MIMES = frozenset({"image/jpeg", "image/png"})
_PDF_MIME = "application/pdf"

# boto3 error codes that mean the blob is simply gone — retrying cannot help.
_PERMANENT_STORAGE_CODES = frozenset({"NoSuchKey", "404", "NoSuchBucket"})


def generate(document: "Document") -> None:
    """Render a thumbnail (PNG, longest side THUMBNAIL_MAX_SIZE) for a document.

    Idempotent: safe to run more than once (overwrites the previous thumbnail), since
    Celery may re-deliver a message. Only PDFs and images are thumbnailed; everything
    else is marked skipped.

    Raises no exception: recoverable storage failures are retried by the caller task
    via TransientError; permanent failures (missing blob, corrupt file) set
    thumbnail_status to failed and return without retrying.
    """
    _set_status(document, ThumbnailStatus.PROCESSING)

    if document.mime_type not in _IMAGE_MIMES and document.mime_type != _PDF_MIME:
        _set_status(document, ThumbnailStatus.SKIPPED)
        logger.info(
            "Thumbnail skipped for %s (mime=%s)", document.pk, document.mime_type
        )
        return

    if not document.storage_path:
        _set_status(document, ThumbnailStatus.SKIPPED)
        logger.warning("Thumbnail skipped for %s (no storage_path)", document.pk)
        return

    blob = _download(document)
    if blob is None:
        return  # already marked failed by _download

    try:
        png_bytes = _render(document.mime_type, blob)
    except Exception:
        _set_status(document, ThumbnailStatus.FAILED)
        logger.exception("Thumbnail rendering failed for %s", document.pk)
        return

    storage = StorageService()
    path = StorageService.build_thumbnail_path(
        str(document.organization_id), str(document.pk)
    )
    storage.upload_file(io.BytesIO(png_bytes), path, content_type="image/png")

    document.thumbnail_key = path
    document.thumbnail_status = ThumbnailStatus.READY
    document.save(update_fields=["thumbnail_key", "thumbnail_status", "updated_at"])

    audit_service.log(
        organization=document.organization,
        user=None,
        entity_type="document",
        entity_id=str(document.pk),
        action=AuditAction.UPDATE,
        new_values={"thumbnail_status": ThumbnailStatus.READY.value},
        metadata={"via": "thumbnail"},
    )
    logger.info("Thumbnail generated for %s", document.pk)


def _download(document: "Document") -> bytes | None:
    """Fetch the blob. Returns None (and marks failed) if it is permanently gone."""
    storage = StorageService()
    try:
        return storage.download_file(document.storage_path)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in _PERMANENT_STORAGE_CODES:
            _set_status(document, ThumbnailStatus.FAILED)
            logger.warning(
                "Thumbnail blob missing for %s (%s); marking failed",
                document.pk,
                code,
            )
            return None
        raise TransientError(
            f"Storage error downloading {document.pk}: {code}"
        ) from exc
    except Exception as exc:  # network/timeout — recoverable
        raise TransientError(f"Storage unavailable for {document.pk}") from exc


def _render(mime_type: str, blob: bytes) -> bytes:
    """Render an image or the first PDF page into a PNG thumbnail and return its bytes."""
    if mime_type in _IMAGE_MIMES:
        image = Image.open(io.BytesIO(blob)).convert("RGB")
    else:
        pages = convert_from_bytes(
            blob,
            dpi=settings.THUMBNAIL_PDF_DPI,
            first_page=1,
            last_page=1,
        )
        image = pages[0].convert("RGB")

    size = settings.THUMBNAIL_MAX_SIZE
    image.thumbnail((size, size))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _set_status(document: "Document", thumbnail_status: ThumbnailStatus) -> None:
    """Persist a status transition without touching the rendered thumbnail."""
    document.thumbnail_status = thumbnail_status
    document.save(update_fields=["thumbnail_status", "updated_at"])
