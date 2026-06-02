from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from apps.audit.models import AuditAction, AuditLog
from apps.core.exceptions import TransientError
from apps.documents.models import OcrStatus
from apps.documents.services import ocr_service
from apps.documents.tests.factories import DocumentFactory
from apps.search.selectors.search_selector import search_documents


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": ""}}, "GetObject")


@pytest.fixture
def mock_storage(monkeypatch):
    """Patch StorageService in ocr_service; return the instance mock."""
    instance = MagicMock()
    instance.download_file.return_value = b"blob-bytes"
    cls = MagicMock(return_value=instance)
    monkeypatch.setattr("apps.documents.services.ocr_service.StorageService", cls)
    return instance


@pytest.mark.django_db
class TestOcrServiceProcess:
    def test_image_is_ocrd_and_completed(self, mock_storage):
        doc = DocumentFactory(mime_type="image/png", ocr_content="")
        with (
            patch("apps.documents.services.ocr_service.Image.open"),
            patch(
                "apps.documents.services.ocr_service.pytesseract.image_to_string",
                return_value="hello from image",
            ),
        ):
            ocr_service.process(doc)
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.COMPLETED
        assert doc.ocr_content == "hello from image"

    def test_pdf_is_ocrd_page_by_page(self, mock_storage):
        doc = DocumentFactory(mime_type="application/pdf", ocr_content="")
        with (
            patch(
                "apps.documents.services.ocr_service.convert_from_bytes",
                return_value=["page1", "page2"],
            ),
            patch(
                "apps.documents.services.ocr_service.pytesseract.image_to_string",
                side_effect=["text one", "text two"],
            ),
        ):
            ocr_service.process(doc)
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.COMPLETED
        assert doc.ocr_content == "text one\ntext two"

    def test_unsupported_mime_is_skipped(self, mock_storage):
        doc = DocumentFactory(
            mime_type="application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
        ocr_service.process(doc)
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.SKIPPED
        mock_storage.download_file.assert_not_called()

    def test_missing_blob_marks_failed_without_retry(self, mock_storage):
        mock_storage.download_file.side_effect = _client_error("NoSuchKey")
        doc = DocumentFactory(mime_type="image/png")
        ocr_service.process(doc)  # must not raise
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.FAILED

    def test_storage_timeout_raises_transient_error(self, mock_storage):
        mock_storage.download_file.side_effect = _client_error("500")
        doc = DocumentFactory(mime_type="image/png")
        with pytest.raises(TransientError):
            ocr_service.process(doc)

    def test_corrupt_file_marks_failed_without_retry(self, mock_storage):
        doc = DocumentFactory(mime_type="image/png")
        with patch(
            "apps.documents.services.ocr_service.Image.open",
            side_effect=OSError("cannot identify image file"),
        ):
            ocr_service.process(doc)  # must not raise
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.FAILED

    def test_blank_page_completes_with_empty_content(self, mock_storage):
        doc = DocumentFactory(mime_type="image/png", ocr_content="old")
        with (
            patch("apps.documents.services.ocr_service.Image.open"),
            patch(
                "apps.documents.services.ocr_service.pytesseract.image_to_string",
                return_value="   ",
            ),
        ):
            ocr_service.process(doc)
        doc.refresh_from_db()
        assert doc.ocr_status == OcrStatus.COMPLETED
        assert doc.ocr_content == ""

    def test_completion_is_audited_with_via_ocr(self, mock_storage):
        doc = DocumentFactory(mime_type="image/png")
        with (
            patch("apps.documents.services.ocr_service.Image.open"),
            patch(
                "apps.documents.services.ocr_service.pytesseract.image_to_string",
                return_value="text",
            ),
        ):
            ocr_service.process(doc)
        log = AuditLog.objects.filter(
            entity_id=str(doc.id), action=AuditAction.UPDATE
        ).latest("created_at")
        assert log.metadata == {"via": "ocr"}
        assert log.user is None  # system action

    def test_document_is_searchable_by_ocr_content(self, mock_storage):
        """The DoD: after OCR, the document is found by a word from its content."""
        doc = DocumentFactory(
            organization__name="Acme", mime_type="image/png", ocr_content=""
        )
        with (
            patch("apps.documents.services.ocr_service.Image.open"),
            patch(
                "apps.documents.services.ocr_service.pytesseract.image_to_string",
                return_value="contrato de arrendamiento confidencial",
            ),
        ):
            ocr_service.process(doc)
        results = search_documents(organization=doc.organization, query="arrendamiento")
        assert doc in list(results)
