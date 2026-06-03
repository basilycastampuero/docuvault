import logging

from celery import shared_task
from django.conf import settings

from apps.core.exceptions import TransientError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.CELERY_TASK_MAX_RETRIES},
)
def process_ocr(self, document_id: str) -> None:
    """Run OCR for a document.

    Thin dispatcher (CLAUDE.md §12): the logic lives in ocr_service. Retries only
    on TransientError (recoverable); any other exception propagates and the task is
    marked failed without retrying. A missing document is treated as permanent — the
    on_commit hook may have fired for a transaction that rolled back.
    """
    # Lazy imports avoid import cycles between tasks and the documents app models.
    from apps.documents.models import Document
    from apps.documents.services import ocr_service

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.warning("process_ocr: document %s not found; skipping", document_id)
        return

    ocr_service.process(document)


@shared_task
def cleanup_orphan_blobs() -> dict:
    """Daily Beat task. Thin dispatcher → cleanup_service (CLAUDE.md §12)."""
    from apps.documents.services import cleanup_service

    return cleanup_service.delete_orphan_blobs()
