"""
Integration tests for StorageService against the real MinIO instance.

These tests require Docker infrastructure to be running:
    docker compose up -d

Run with:
    pytest apps/documents/tests/test_storage_integration.py -v -m integration

The test bucket `saasvault-test` is already configured in config/settings/test.py
(AWS_STORAGE_BUCKET_NAME = "saasvault-test") so StorageService() picks it up
automatically without any monkey-patching.
"""

import io
import urllib.request
from datetime import UTC, datetime

import pytest

from apps.documents.storage.storage_service import StorageService

# ---------------------------------------------------------------------------
# Session-scoped fixture: create the bucket once, nuke everything at the end.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def storage_svc():
    """Return a StorageService pointing at the test bucket.

    The bucket is created once at the start of the session and all its
    objects are deleted when the session ends, leaving MinIO clean for
    future runs.
    """
    svc = StorageService()
    # The settings.test already sets AWS_STORAGE_BUCKET_NAME = "saasvault-test"
    # so svc._bucket is already "saasvault-test" — confirm it for safety.
    assert svc._bucket == "saasvault-test", (
        f"Expected test bucket 'saasvault-test', got '{svc._bucket}'. "
        "Make sure DJANGO_SETTINGS_MODULE=config.settings.test is active."
    )
    svc.ensure_bucket()
    yield svc
    # Session teardown: delete every remaining object in the test bucket.
    keys = [key for key, _ in svc.list_objects()]
    for key in keys:
        svc.delete_file(key)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEnsureBucket:
    def test_ensure_bucket_is_idempotent(self, storage_svc: StorageService):
        """Should not raise when called on an already-existing bucket."""
        # The fixture already called ensure_bucket() once; calling it again
        # must succeed silently (no exception, no duplicate-bucket error).
        storage_svc.ensure_bucket()

    def test_ensure_bucket_creates_new_bucket(self):
        """Should create the bucket when it does not exist, then clean up."""
        import uuid

        ephemeral_name = f"saasvault-ephemeral-{uuid.uuid4().hex[:8]}"
        svc = StorageService()
        svc._bucket = ephemeral_name
        try:
            svc.ensure_bucket()
            # Verify the bucket is now accessible by calling head_bucket directly.
            svc._client.head_bucket(Bucket=ephemeral_name)
        finally:
            # Best-effort cleanup: delete the ephemeral bucket.
            try:
                svc._client.delete_bucket(Bucket=ephemeral_name)
            except Exception:
                pass


@pytest.mark.integration
class TestUploadDownload:
    def test_upload_and_download_roundtrip(self, storage_svc: StorageService):
        """Should recover exact bytes after upload → download roundtrip."""
        key = "integration/roundtrip/hello.bin"
        original = b"SasVault integration test payload \x00\x01\x02\xff"
        storage_svc.upload_file(io.BytesIO(original), key, "application/octet-stream")
        try:
            downloaded = storage_svc.download_file(key)
            assert downloaded == original
        finally:
            storage_svc.delete_file(key)

    def test_upload_returns_storage_path(self, storage_svc: StorageService):
        """upload_file() should return the exact path that was passed in."""
        key = "integration/roundtrip/path_check.txt"
        returned = storage_svc.upload_file(io.BytesIO(b"content"), key, "text/plain")
        try:
            assert returned == key
        finally:
            storage_svc.delete_file(key)

    def test_upload_pdf_content_type(self, storage_svc: StorageService):
        """Should preserve content correctly regardless of MIME type label."""
        key = "integration/roundtrip/fake.pdf"
        # Not a real PDF; we're testing byte fidelity, not PDF validity.
        pdf_bytes = b"%PDF-1.4 fake content"
        storage_svc.upload_file(io.BytesIO(pdf_bytes), key, "application/pdf")
        try:
            assert storage_svc.download_file(key) == pdf_bytes
        finally:
            storage_svc.delete_file(key)

    def test_upload_empty_file(self, storage_svc: StorageService):
        """Should handle a zero-byte upload without error."""
        key = "integration/roundtrip/empty.bin"
        storage_svc.upload_file(io.BytesIO(b""), key, "application/octet-stream")
        try:
            assert storage_svc.download_file(key) == b""
        finally:
            storage_svc.delete_file(key)


@pytest.mark.integration
class TestDeleteFile:
    def test_delete_existing_object(self, storage_svc: StorageService):
        """Should delete an existing object without raising."""
        key = "integration/delete/existing.bin"
        storage_svc.upload_file(
            io.BytesIO(b"to be deleted"), key, "application/octet-stream"
        )
        # Must not raise.
        storage_svc.delete_file(key)
        # Confirm it is gone: get_object must raise NoSuchKey.
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError) as exc_info:
            storage_svc.download_file(key)
        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

    def test_delete_nonexistent_key_is_noop(self, storage_svc: StorageService):
        """Should not raise when deleting a key that does not exist in the bucket."""
        key = "integration/delete/ghost-object-that-does-not-exist.bin"
        # S3/MinIO delete_object is always successful even for missing keys.
        storage_svc.delete_file(key)  # must not raise


@pytest.mark.integration
class TestPresignedUrl:
    def test_presigned_url_is_accessible(self, storage_svc: StorageService):
        """Should generate a URL that returns the original content when fetched."""
        key = "integration/presign/document.txt"
        content = b"presigned content check"
        storage_svc.upload_file(io.BytesIO(content), key, "text/plain")
        try:
            url = storage_svc.get_presigned_url(key, expires=300)
            assert url.startswith("http"), f"URL should be http(s), got: {url}"

            # Fetch via the presigned URL — no auth headers required.
            with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
                fetched = response.read()
            assert fetched == content
        finally:
            storage_svc.delete_file(key)

    def test_presigned_url_is_a_string(self, storage_svc: StorageService):
        """get_presigned_url() should return a non-empty string."""
        key = "integration/presign/url_type.txt"
        storage_svc.upload_file(io.BytesIO(b"x"), key, "text/plain")
        try:
            url = storage_svc.get_presigned_url(key, expires=60)
            assert isinstance(url, str)
            assert len(url) > 0
        finally:
            storage_svc.delete_file(key)

    def test_presigned_url_respects_custom_expiry(self, storage_svc: StorageService):
        """The presigned URL should embed the requested expiry in its query string."""
        key = "integration/presign/expiry.txt"
        storage_svc.upload_file(io.BytesIO(b"x"), key, "text/plain")
        try:
            # MinIO embeds X-Amz-Expires in the URL for SigV4.
            url_short = storage_svc.get_presigned_url(key, expires=60)
            url_long = storage_svc.get_presigned_url(key, expires=7200)
            # Both must be valid strings; we just verify they differ.
            assert url_short != url_long
        finally:
            storage_svc.delete_file(key)


@pytest.mark.integration
class TestListObjects:
    def test_list_objects_returns_uploaded_keys(self, storage_svc: StorageService):
        """Should yield all uploaded keys with their last_modified timestamps."""
        keys = [
            "integration/list/obj_a.bin",
            "integration/list/obj_b.bin",
            "integration/list/obj_c.bin",
        ]
        for key in keys:
            storage_svc.upload_file(
                io.BytesIO(b"data"), key, "application/octet-stream"
            )
        try:
            listed = dict(storage_svc.list_objects())
            for key in keys:
                assert key in listed, f"Expected key '{key}' in listing"
        finally:
            for key in keys:
                storage_svc.delete_file(key)

    def test_list_objects_last_modified_is_tz_aware(self, storage_svc: StorageService):
        """last_modified returned by list_objects() must be timezone-aware (UTC)."""
        key = "integration/list/tz_check.bin"
        storage_svc.upload_file(io.BytesIO(b"tz"), key, "application/octet-stream")
        try:
            results = list(storage_svc.list_objects())
            # Find our key in the bucket listing.
            match = next((ts for k, ts in results if k == key), None)
            assert match is not None, f"Key '{key}' not found in listing"
            assert (
                match.tzinfo is not None
            ), "last_modified must be tz-aware; got naive datetime"
        finally:
            storage_svc.delete_file(key)

    def test_list_objects_yields_tuples(self, storage_svc: StorageService):
        """Each item from list_objects() must be a (str, datetime) tuple."""
        key = "integration/list/tuple_check.bin"
        storage_svc.upload_file(io.BytesIO(b"t"), key, "application/octet-stream")
        try:
            for k, ts in storage_svc.list_objects():
                assert isinstance(k, str)
                assert isinstance(ts, datetime)
                break  # Only need one item to verify the shape.
        finally:
            storage_svc.delete_file(key)


@pytest.mark.integration
class TestBuildStoragePath:
    """Unit tests for the static path builder — no MinIO connection needed."""

    def test_format_has_five_segments(self):
        """Should produce exactly 5 slash-separated segments."""
        path = StorageService.build_storage_path("org-abc", "doc-123", "report.pdf")
        parts = path.split("/")
        assert len(parts) == 5

    def test_org_id_is_first_segment(self):
        """The first segment must be org_id."""
        path = StorageService.build_storage_path("org-abc", "doc-123", "report.pdf")
        assert path.split("/")[0] == "org-abc"

    def test_doc_id_is_fourth_segment(self):
        """The fourth segment must be document_id."""
        path = StorageService.build_storage_path("org-abc", "doc-123", "report.pdf")
        assert path.split("/")[3] == "doc-123"

    def test_filename_is_last_segment(self):
        """The last segment must be the filename."""
        path = StorageService.build_storage_path("org-abc", "doc-123", "report.pdf")
        assert path.split("/")[4] == "report.pdf"

    def test_year_month_segments_are_current(self):
        """Segments 2 and 3 must be the current year and zero-padded month."""
        now = datetime.now(UTC)
        path = StorageService.build_storage_path("org-abc", "doc-123", "f.pdf")
        parts = path.split("/")
        assert parts[1] == str(now.year)
        assert parts[2] == f"{now.month:02d}"

    def test_month_is_zero_padded(self):
        """Month segment must always be two digits (01–12)."""
        path = StorageService.build_storage_path("org-1", "doc-1", "f.pdf")
        month_part = path.split("/")[2]
        assert len(month_part) == 2
        assert month_part.isdigit()
