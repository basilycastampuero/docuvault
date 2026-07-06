import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from apps.audit.models import AuditAction, AuditLog
from apps.core.exceptions import TransientError
from apps.documents.models import ThumbnailStatus
from apps.documents.services import thumbnail_service
from apps.documents.tests.factories import DocumentFactory


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": ""}}, "GetObject")


def _real_png_bytes(size: tuple[int, int] = (20, 20)) -> bytes:
    """Build genuine PNG bytes (no mocking of Pillow) for end-to-end render tests."""
    buf = io.BytesIO()
    Image.new("RGB", size, color="blue").save(buf, format="PNG")
    return buf.getvalue()


def _real_pdf_bytes(pages: int = 1, size: tuple[int, int] = (30, 30)) -> bytes:
    """Build a genuine single/multi-page PDF via Pillow (no reportlab dependency).

    poppler (pdftoppm) is required at the OS level for pdf2image to render this back
    — already a project dependency (CLAUDE.md §4.0 OCR deps).
    """
    buf = io.BytesIO()
    images = [Image.new("RGB", size, color="red") for _ in range(pages)]
    first, rest = images[0], images[1:]
    if rest:
        first.save(buf, format="PDF", save_all=True, append_images=rest)
    else:
        first.save(buf, format="PDF")
    return buf.getvalue()


@pytest.fixture
def mock_storage(monkeypatch):
    """Patch StorageService in thumbnail_service; return the instance mock.

    `build_thumbnail_path` is a staticmethod invoked on the class itself
    (`StorageService.build_thumbnail_path(...)`), so the mock class must keep the
    real implementation — otherwise it resolves to a MagicMock instead of a string.
    """
    from apps.documents.storage.storage_service import (
        StorageService as RealStorageService,
    )

    instance = MagicMock()
    instance.download_file.return_value = b"blob-bytes"
    cls = MagicMock(return_value=instance)
    cls.build_thumbnail_path = RealStorageService.build_thumbnail_path
    monkeypatch.setattr("apps.documents.services.thumbnail_service.StorageService", cls)
    return instance


@pytest.mark.django_db
class TestThumbnailServiceGenerate:
    def test_pdf_generates_real_thumbnail_and_uploads(self, mock_storage):
        """Real PDF bytes (via Pillow+poppler) are rendered to a real PNG and uploaded."""
        mock_storage.download_file.return_value = _real_pdf_bytes()
        doc = DocumentFactory(mime_type="application/pdf")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.READY
        assert doc.thumbnail_key != ""
        mock_storage.upload_file.assert_called_once()
        args, kwargs = mock_storage.upload_file.call_args
        uploaded_bytes = args[0].getvalue()
        # Prove it is a real PNG, not a stub.
        rendered = Image.open(io.BytesIO(uploaded_bytes))
        assert rendered.format == "PNG"
        assert kwargs["content_type"] == "image/png"

    def test_image_jpeg_generates_ready_thumbnail(self, mock_storage):
        mock_storage.download_file.return_value = _real_png_bytes()
        doc = DocumentFactory(mime_type="image/jpeg")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.READY
        assert doc.thumbnail_key != ""

    def test_image_png_generates_ready_thumbnail(self, mock_storage):
        mock_storage.download_file.return_value = _real_png_bytes()
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.READY

    def test_thumbnail_is_resized_to_max_size(self, mock_storage, settings):
        """Rendered thumbnail must be capped at THUMBNAIL_MAX_SIZE on its longest side."""
        settings.THUMBNAIL_MAX_SIZE = 10
        mock_storage.download_file.return_value = _real_png_bytes(size=(500, 200))
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)

        uploaded_bytes = mock_storage.upload_file.call_args[0][0].getvalue()
        rendered = Image.open(io.BytesIO(uploaded_bytes))
        assert max(rendered.size) <= 10

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword",
            "application/zip",
        ],
    )
    def test_unsupported_mime_is_skipped(self, mock_storage, mime_type):
        doc = DocumentFactory(mime_type=mime_type)

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.SKIPPED
        mock_storage.download_file.assert_not_called()

    def test_empty_storage_path_is_skipped_not_failed(self, mock_storage):
        """A document with no blob yet (upload race) must be skipped, not failed."""
        doc = DocumentFactory(mime_type="application/pdf", storage_path="")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.SKIPPED
        mock_storage.download_file.assert_not_called()

    def test_missing_blob_marks_failed_without_retry(self, mock_storage):
        mock_storage.download_file.side_effect = _client_error("NoSuchKey")
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)  # must not raise

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.FAILED

    def test_storage_timeout_raises_transient_error(self, mock_storage):
        mock_storage.download_file.side_effect = _client_error("500")
        doc = DocumentFactory(mime_type="image/png")

        with pytest.raises(TransientError):
            thumbnail_service.generate(doc)

    def test_network_error_raises_transient_error(self, mock_storage):
        mock_storage.download_file.side_effect = ConnectionError("timeout")
        doc = DocumentFactory(mime_type="application/pdf")

        with pytest.raises(TransientError):
            thumbnail_service.generate(doc)

    def test_corrupt_image_marks_failed_without_retry(self, mock_storage):
        mock_storage.download_file.return_value = b"not-a-real-image"
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)  # must not raise

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.FAILED
        mock_storage.upload_file.assert_not_called()

    def test_corrupt_pdf_marks_failed_without_retry(self, mock_storage):
        mock_storage.download_file.return_value = b"%PDF-not-really-valid-bytes"
        doc = DocumentFactory(mime_type="application/pdf")

        thumbnail_service.generate(doc)  # must not raise

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.FAILED
        mock_storage.upload_file.assert_not_called()

    def test_pdf_render_only_processes_first_page(self, mock_storage):
        """Critical performance requirement: never render more than page 1."""
        doc = DocumentFactory(mime_type="application/pdf")
        with patch(
            "apps.documents.services.thumbnail_service.convert_from_bytes",
            return_value=[Image.new("RGB", (10, 10))],
        ) as mock_convert:
            thumbnail_service.generate(doc)

        mock_convert.assert_called_once()
        _, kwargs = mock_convert.call_args
        assert kwargs["first_page"] == 1
        assert kwargs["last_page"] == 1

    def test_multi_page_pdf_thumbnail_reflects_only_first_page(self, mock_storage):
        """Even with a real multi-page PDF, only the first page is thumbnailed."""
        mock_storage.download_file.return_value = _real_pdf_bytes(pages=3)
        doc = DocumentFactory(mime_type="application/pdf")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.READY
        # A single-image PNG was uploaded (convert_from_bytes with last_page=1 never
        # yields more than one page, so there is nothing to composite beyond page 1).
        mock_storage.upload_file.assert_called_once()

    def test_completion_is_audited_with_via_thumbnail(self, mock_storage):
        mock_storage.download_file.return_value = _real_png_bytes()
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)

        log = AuditLog.objects.filter(
            entity_id=str(doc.id), action=AuditAction.UPDATE
        ).latest("created_at")
        assert log.metadata == {"via": "thumbnail"}
        assert log.user is None  # system action

    def test_thumbnail_key_uses_build_thumbnail_path_format(self, mock_storage):
        mock_storage.download_file.return_value = _real_png_bytes()
        doc = DocumentFactory(mime_type="image/png")

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_key.endswith("/thumbnails/thumb.png")
        assert str(doc.organization_id) in doc.thumbnail_key
        assert str(doc.pk) in doc.thumbnail_key

    def test_generate_is_idempotent_overwrites_previous_thumbnail(self, mock_storage):
        """A second run must overwrite (not fail on) a document already marked ready."""
        mock_storage.download_file.return_value = _real_png_bytes()
        doc = DocumentFactory(
            mime_type="image/png",
            thumbnail_status=ThumbnailStatus.READY,
            thumbnail_key="old/key.png",
        )

        thumbnail_service.generate(doc)

        doc.refresh_from_db()
        assert doc.thumbnail_status == ThumbnailStatus.READY
        assert doc.thumbnail_key != "old/key.png"
        assert mock_storage.upload_file.call_count == 1
