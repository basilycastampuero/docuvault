import uuid
from unittest.mock import patch

import pytest
from celery.exceptions import Retry

from apps.core.exceptions import TransientError
from apps.documents.tasks.document_tasks import (
    analyze_document,
    cleanup_orphan_blobs,
    generate_thumbnail,
    process_ocr,
)
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


@pytest.mark.django_db
class TestAnalyzeDocumentTask:
    def test_delegates_to_ai_service(self):
        """Thin task: must call ai_service.analyze with the document."""
        doc = DocumentFactory()
        with patch("apps.documents.services.ai_service.analyze") as mock_analyze:
            result = analyze_document.apply(args=[str(doc.id)])
        assert result.successful()
        mock_analyze.assert_called_once()
        assert mock_analyze.call_args.args[0].id == doc.id

    def test_missing_document_skips_without_error(self):
        """A doc that does not exist causes the task to skip gracefully."""
        with patch("apps.documents.services.ai_service.analyze") as mock_analyze:
            result = analyze_document.apply(args=[str(uuid.uuid4())])
        assert result.successful()
        mock_analyze.assert_not_called()

    def test_transient_error_triggers_retry(self):
        """TransientError from ai_service routes through the retry machinery."""
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.ai_service.analyze",
            side_effect=TransientError("model timeout"),
        ):
            with pytest.raises(Retry):
                analyze_document.apply(args=[str(doc.id)])

    def test_permanent_error_writes_failure_marker(self):
        """A non-transient error writes a failure marker to document.metadata."""
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.ai_service.analyze",
            side_effect=RuntimeError("unexpected failure"),
        ):
            with pytest.raises(RuntimeError):
                analyze_document.apply(args=[str(doc.id)])

        doc.refresh_from_db()
        ai = doc.metadata.get("ai_analysis", {})
        assert ai["status"] == "failed"
        assert "error" in ai

    def test_permanent_error_failure_marker_does_not_affect_other_metadata(self):
        """Failure marker write leaves other metadata fields intact."""
        doc = DocumentFactory()
        doc.metadata["custom_field"] = "preserved"
        doc.save(update_fields=["metadata"])

        with patch(
            "apps.documents.services.ai_service.analyze",
            side_effect=ValueError("corrupt data"),
        ):
            with pytest.raises(ValueError):
                analyze_document.apply(args=[str(doc.id)])

        doc.refresh_from_db()
        assert doc.metadata["custom_field"] == "preserved"
        assert doc.metadata["ai_analysis"]["status"] == "failed"


@pytest.mark.django_db
class TestGenerateThumbnailTask:
    def test_happy_path_calls_service_with_document(self):
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.thumbnail_service.generate"
        ) as mock_generate:
            result = generate_thumbnail.apply(args=[str(doc.id)])
        assert result.successful()
        mock_generate.assert_called_once()
        assert mock_generate.call_args.args[0].id == doc.id

    def test_transient_error_triggers_retry(self):
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.thumbnail_service.generate",
            side_effect=TransientError("storage timeout"),
        ) as mock_generate:
            with pytest.raises(Retry):
                generate_thumbnail.apply(args=[str(doc.id)])
        mock_generate.assert_called_once()

    def test_permanent_error_propagates_without_retry(self):
        doc = DocumentFactory()
        with patch(
            "apps.documents.services.thumbnail_service.generate",
            side_effect=ValueError("corrupt file"),
        ) as mock_generate:
            with pytest.raises(ValueError):
                generate_thumbnail.apply(args=[str(doc.id)])
        mock_generate.assert_called_once()

    def test_missing_document_skips_without_error(self):
        with patch(
            "apps.documents.services.thumbnail_service.generate"
        ) as mock_generate:
            result = generate_thumbnail.apply(args=[str(uuid.uuid4())])
        assert result.successful()
        mock_generate.assert_not_called()


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
