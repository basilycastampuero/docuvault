import uuid
from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from apps.core.exceptions import TransientError
from apps.documents.tasks.document_tasks import cleanup_orphan_blobs, process_ocr
from apps.documents.tests.factories import DocumentFactory

# Tasks run synchronously here (CELERY_TASK_ALWAYS_EAGER + EAGER_PROPAGATES). In
# eager mode there is no broker to reschedule, so self.retry() raises Retry instead
# of looping. That is enough to prove the *policy*: a TransientError is routed
# through the retry machinery (would retry in production), while any other error
# propagates as-is without ever being retried.


@pytest.mark.django_db
class TestProcessOcrTask:
    def test_happy_path_calls_service_with_document(self):
        doc = DocumentFactory()
        with patch("apps.documents.services.ocr_service.process") as mock_process:
            result = process_ocr.apply(args=[str(doc.id)])
        assert result.successful()
        mock_process.assert_called_once()
        assert mock_process.call_args.args[0].id == doc.id

    def test_transient_error_triggers_retry(self):
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.ocr_service.process",
            side_effect=TransientError("storage timeout"),
        ) as mock_process:
            with pytest.raises(Retry):
                process_ocr.apply(args=[str(doc.id)])
        mock_process.assert_called_once()

    def test_permanent_error_propagates_without_retry(self):
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.ocr_service.process",
            side_effect=ValueError("corrupt file"),
        ) as mock_process:
            with pytest.raises(ValueError):
                process_ocr.apply(args=[str(doc.id)])
        mock_process.assert_called_once()

    def test_missing_document_skips_without_error(self):
        with patch("apps.documents.services.ocr_service.process") as mock_process:
            result = process_ocr.apply(args=[str(uuid.uuid4())])
        assert result.successful()
        mock_process.assert_not_called()


class TestCleanupOrphanBlobsTask:
    def test_task_delegates_to_cleanup_service(self):
        """Thin task: must call cleanup_service.delete_orphan_blobs and return its result."""
        expected = {"scanned": 5, "deleted": 2, "skipped_grace": 1}
        with patch(
            "apps.documents.services.cleanup_service.delete_orphan_blobs",
            return_value=expected,
        ) as mock_cleanup:
            result = cleanup_orphan_blobs.apply()
        assert result.successful()
        mock_cleanup.assert_called_once_with()
        assert result.get() == expected
