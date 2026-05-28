import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def process_ocr(document_id: str) -> None:
    """OCR stub — body implemented in Phase 4.2."""
    logger.info("OCR stub invoked for document %s", document_id)
