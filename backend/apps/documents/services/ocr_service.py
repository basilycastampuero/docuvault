import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.documents.models import Document

logger = logging.getLogger(__name__)


def process(document: "Document") -> None:
    """Extract text from a document via OCR and index it.

    Idempotent: safe to run more than once (overwrites the previous result), since
    Celery may re-deliver a message. The real OCR body lands in Phase 4.2; for now
    this is a thin placeholder so the task wiring and retry policy can be exercised.
    """
    logger.info("OCR stub for document %s", document.pk)
