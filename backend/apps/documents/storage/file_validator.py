import hashlib
from typing import IO

import magic
from django.conf import settings

from apps.core.exceptions import ValidationError


def validate_file(file: IO[bytes]) -> tuple[str, int, str]:
    """
    Validate an uploaded file and return (mime_type, size_bytes, sha256_hex).

    Checks size limit first, then detects MIME type from magic bytes (not
    extension), then streams the full file to compute the SHA-256 checksum.
    Rewinds the file to position 0 before returning so callers can read it again.
    """
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    max_size: int = getattr(settings, "MAX_UPLOAD_SIZE", 50 * 1024 * 1024)
    if size > max_size:
        raise ValidationError(
            message=f"File size {size} bytes exceeds the maximum of {max_size} bytes.",
            code="FILE_TOO_LARGE",
        )

    header = file.read(2048)
    file.seek(0)
    detected_mime: str = magic.from_buffer(header, mime=True)

    allowed: frozenset[str] = getattr(
        settings, "ALLOWED_UPLOAD_MIME_TYPES", frozenset()
    )
    if detected_mime not in allowed:
        raise ValidationError(
            message=f"File type '{detected_mime}' is not allowed.",
            code="INVALID_MIME_TYPE",
        )

    hasher = hashlib.sha256()
    while chunk := file.read(65536):
        hasher.update(chunk)
    checksum = hasher.hexdigest()

    file.seek(0)
    return detected_mime, size, checksum
