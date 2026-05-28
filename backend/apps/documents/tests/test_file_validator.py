import hashlib
import io

import pytest

from apps.core.exceptions import ValidationError
from apps.documents.storage.file_validator import validate_file


def _make_file(content: bytes) -> io.BytesIO:
    return io.BytesIO(content)


# Real PDF magic bytes
PDF_HEADER = b"%PDF-1.4\n" + b"%" * 100


@pytest.mark.django_db
class TestFileValidator:
    def test_valid_pdf_returns_mime_size_checksum(self):
        content = PDF_HEADER + b"x" * 1000
        f = _make_file(content)
        mime, size, checksum = validate_file(f)
        assert mime == "application/pdf"
        assert size == len(content)
        assert len(checksum) == 64

    def test_checksum_is_stable(self):
        content = PDF_HEADER + b"stable"
        _, _, c1 = validate_file(_make_file(content))
        _, _, c2 = validate_file(_make_file(content))
        assert c1 == c2

    def test_checksum_matches_sha256(self):
        content = PDF_HEADER + b"check"
        f = _make_file(content)
        _, _, checksum = validate_file(f)
        expected = hashlib.sha256(content).hexdigest()
        assert checksum == expected

    def test_file_is_rewound_after_validation(self):
        content = PDF_HEADER + b"rewind"
        f = _make_file(content)
        validate_file(f)
        assert f.tell() == 0

    def test_file_too_large_raises(self, settings):
        settings.MAX_UPLOAD_SIZE = 100
        content = b"x" * 200
        with pytest.raises(ValidationError) as exc_info:
            validate_file(_make_file(content))
        assert exc_info.value.code == "FILE_TOO_LARGE"

    def test_disallowed_mime_raises(self, settings):
        settings.ALLOWED_UPLOAD_MIME_TYPES = frozenset({"application/pdf"})
        # PNG magic bytes — should be rejected
        content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        with pytest.raises(ValidationError) as exc_info:
            validate_file(_make_file(content))
        assert exc_info.value.code == "INVALID_MIME_TYPE"

    def test_disguised_exe_detected_by_magic(self, settings):
        """A file renamed to .pdf but containing EXE magic bytes must be rejected."""
        settings.ALLOWED_UPLOAD_MIME_TYPES = frozenset({"application/pdf"})
        # Windows PE magic bytes (MZ header)
        content = b"MZ" + b"\x00" * 200
        with pytest.raises(ValidationError) as exc_info:
            validate_file(_make_file(content))
        assert exc_info.value.code == "INVALID_MIME_TYPE"

    def test_empty_file_raises(self, settings):
        settings.ALLOWED_UPLOAD_MIME_TYPES = frozenset({"application/pdf"})
        with pytest.raises(ValidationError):
            validate_file(_make_file(b""))
