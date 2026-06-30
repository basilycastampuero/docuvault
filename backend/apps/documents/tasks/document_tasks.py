import logging

from celery import shared_task

from apps.core.exceptions import TransientError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
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


@shared_task(
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def analyze_document(self, document_id: str) -> None:
    """Run AI analysis for a document.

    Thin dispatcher (CLAUDE.md §12): the logic lives in ai_service. Retries only
    on TransientError (recoverable, e.g. malformed model response); any other
    exception propagates and the task is marked failed without retrying. A missing
    document is treated as permanent — the on_commit hook may have fired for a
    transaction that rolled back.

    On permanent failure (non-transient exception, or TransientError after all
    retries exhausted) a sentinel is written to document.metadata["ai_analysis"]
    so the frontend polling loop can stop and display an error state.
    """
    from apps.documents.models import Document
    from apps.documents.services import ai_service

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.warning("analyze_document: document %s not found; skipping", document_id)
        return

    try:
        ai_service.analyze(document)
    except TransientError:
        # autoretry_for handles the retry scheduling. On the final retry attempt
        # (retries == max_retries), autoretry_for will raise MaxRetriesExceededError
        # after we re-raise here. Write the failure marker now so the frontend
        # stops polling before that exception propagates.
        if self.request.retries >= self.max_retries:
            _write_ai_failure_marker(document, document_id)
        raise
    except Exception:
        # Non-transient permanent failure — write marker immediately and propagate.
        _write_ai_failure_marker(document, document_id)
        raise


def _write_ai_failure_marker(document, document_id: str) -> None:
    """Persist a failure sentinel in document.metadata so the frontend can stop polling."""
    document.metadata["ai_analysis"] = {
        "status": "failed",
        "error": "Analysis failed permanently",
    }
    document.save(update_fields=["metadata", "updated_at"])
    logger.error("AI analysis permanently failed for document %s", document_id)


@shared_task
def cleanup_orphan_blobs() -> dict:
    """Daily Beat task. Thin dispatcher → cleanup_service (CLAUDE.md §12)."""
    from apps.documents.services import cleanup_service

    return cleanup_service.delete_orphan_blobs()
