"""
End-to-end integration test for cleanup_service.delete_orphan_blobs().

Requires both PostgreSQL (real DB) and MinIO (real object storage) to be running:
    docker compose up -d

Run with:
    pytest apps/documents/tests/test_cleanup_integration.py -v -m integration

Design choices:
- The fixture `live_storage` is function-scoped so each test starts with a clean
  bucket state (all objects from previous test are removed in teardown).
- `grace_hours=0` bypasses the grace window so recently-uploaded blobs are also
  eligible for deletion, making tests deterministic without needing time travel.
- The test bucket 'saasvault-test' is already set in config/settings/test.py, so
  StorageService() automatically points to the right bucket.
"""

import io

import pytest

from apps.documents.services import cleanup_service
from apps.documents.storage.storage_service import StorageService
from apps.documents.tests.factories import DocumentFactory, DocumentVersionFactory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cleanup_storage_session():
    """Create the test bucket once for the entire session.

    Each test function is responsible for cleaning up its own objects;
    this session fixture only handles bucket creation.
    """
    svc = StorageService()
    assert svc._bucket == "saasvault-test"
    svc.ensure_bucket()
    yield svc


@pytest.fixture
def live_storage(cleanup_storage_session):
    """Function-scoped: yield a clean StorageService, then wipe all test objects.

    Teardown removes all objects that accumulated during the test, keeping the
    bucket ready for the next test regardless of failures.
    """
    svc = cleanup_storage_session
    yield svc
    # Teardown: delete every remaining object in the test bucket.
    keys = [key for key, _ in svc.list_objects()]
    for key in keys:
        svc.delete_file(key)


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestCleanupIntegration:
    def test_live_document_blob_is_kept(self, live_storage: StorageService):
        """Blob referenced by a live document must survive cleanup."""
        content = b"live document content"
        key = "integration/cleanup/live_doc.pdf"
        live_storage.upload_file(io.BytesIO(content), key, "application/pdf")

        # Create a live document pointing at this blob.
        DocumentFactory(storage_path=key)

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        # The blob must still be downloadable.
        assert live_storage.download_file(key) == content
        assert result["deleted"] == 0

    def test_soft_deleted_document_blob_is_removed(self, live_storage: StorageService):
        """Blob of a soft-deleted document must be deleted by cleanup."""
        key = "integration/cleanup/deleted_doc.pdf"
        live_storage.upload_file(io.BytesIO(b"deleted doc"), key, "application/pdf")

        doc = DocumentFactory(storage_path=key)
        doc.soft_delete()

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result["deleted"] >= 1
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError) as exc_info:
            live_storage.download_file(key)
        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

    def test_version_blob_of_live_doc_is_kept(self, live_storage: StorageService):
        """DocumentVersion blob whose parent Document is alive must be kept."""
        doc_key = "integration/cleanup/live_doc_with_ver.pdf"
        ver_key = "integration/cleanup/live_doc_v1.pdf"

        live_storage.upload_file(io.BytesIO(b"doc content"), doc_key, "application/pdf")
        live_storage.upload_file(io.BytesIO(b"ver content"), ver_key, "application/pdf")

        doc = DocumentFactory(storage_path=doc_key)
        DocumentVersionFactory(document=doc, storage_path=ver_key, version_number=1)

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result["deleted"] == 0
        # Both blobs must still be accessible.
        assert live_storage.download_file(doc_key) == b"doc content"
        assert live_storage.download_file(ver_key) == b"ver content"

    def test_orphan_blob_without_db_reference_is_removed(
        self, live_storage: StorageService
    ):
        """Blob with no Document or DocumentVersion row must be deleted."""
        orphan_key = "integration/cleanup/orphan_no_db_ref.pdf"
        live_storage.upload_file(
            io.BytesIO(b"orphan data"), orphan_key, "application/pdf"
        )
        # No DB record created for this blob.

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result["deleted"] >= 1
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError) as exc_info:
            live_storage.download_file(orphan_key)
        assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")

    def test_e2e_mixed_scenario(self, live_storage: StorageService):
        """Full scenario: live doc, soft-deleted doc with version, pure orphan.

        After cleanup(grace=0):
          - live doc blob: kept
          - live doc version blob: kept
          - soft-deleted doc blob: removed
          - version blob of soft-deleted doc: removed
          - pure orphan blob: removed
        """
        live_doc_key = "integration/cleanup/e2e_live_doc.pdf"
        live_ver_key = "integration/cleanup/e2e_live_ver.pdf"
        dead_doc_key = "integration/cleanup/e2e_dead_doc.pdf"
        dead_ver_key = "integration/cleanup/e2e_dead_ver.pdf"
        orphan_key = "integration/cleanup/e2e_orphan.pdf"

        for key in (live_doc_key, live_ver_key, dead_doc_key, dead_ver_key, orphan_key):
            live_storage.upload_file(io.BytesIO(b"data"), key, "application/pdf")

        # Live document + its version.
        live_doc = DocumentFactory(storage_path=live_doc_key)
        DocumentVersionFactory(
            document=live_doc, storage_path=live_ver_key, version_number=1
        )

        # Soft-deleted document + its version (version is also an orphan now).
        dead_doc = DocumentFactory(storage_path=dead_doc_key)
        DocumentVersionFactory(
            document=dead_doc, storage_path=dead_ver_key, version_number=1
        )
        dead_doc.soft_delete()

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        # Exactly 3 blobs must have been deleted: dead_doc, dead_ver, orphan.
        assert result["scanned"] == 5
        assert result["deleted"] == 3
        assert result["skipped_grace"] == 0

        # Live blobs still accessible.
        assert live_storage.download_file(live_doc_key) == b"data"
        assert live_storage.download_file(live_ver_key) == b"data"

        # Dead blobs must be gone.
        from botocore.exceptions import ClientError

        for dead_key in (dead_doc_key, dead_ver_key, orphan_key):
            with pytest.raises(ClientError) as exc_info:
                live_storage.download_file(dead_key)
            assert exc_info.value.response["Error"]["Code"] in (
                "NoSuchKey",
                "404",
            ), f"Expected key '{dead_key}' to be deleted"

    def test_cleanup_returns_correct_summary_dict(self, live_storage: StorageService):
        """The summary dict must have the correct scanned/deleted/skipped_grace keys."""
        orphan_key = "integration/cleanup/summary_orphan.pdf"
        live_storage.upload_file(io.BytesIO(b"x"), orphan_key, "application/pdf")

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert set(result.keys()) == {"scanned", "deleted", "skipped_grace"}
        assert isinstance(result["scanned"], int)
        assert isinstance(result["deleted"], int)
        assert isinstance(result["skipped_grace"], int)

    def test_empty_bucket_returns_zero_counts(self, live_storage: StorageService):
        """With an empty bucket, summary must be all zeros."""
        # live_storage fixture guarantees a clean bucket at the start of each test.
        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result == {"scanned": 0, "deleted": 0, "skipped_grace": 0}

    def test_live_document_thumbnail_is_kept(self, live_storage: StorageService):
        """A live document's thumbnail blob must survive cleanup, same as its file."""
        doc_key = "integration/cleanup/thumb_live_doc.pdf"
        thumb_key = "integration/cleanup/thumb_live_doc/thumbnails/thumb.png"
        live_storage.upload_file(io.BytesIO(b"doc content"), doc_key, "application/pdf")
        live_storage.upload_file(io.BytesIO(b"thumb bytes"), thumb_key, "image/png")

        DocumentFactory(storage_path=doc_key, thumbnail_key=thumb_key)

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result["deleted"] == 0
        assert live_storage.download_file(doc_key) == b"doc content"
        assert live_storage.download_file(thumb_key) == b"thumb bytes"

    def test_soft_deleted_document_thumbnail_is_removed_after_grace(
        self, live_storage: StorageService
    ):
        """A soft-deleted document's thumbnail blob must be swept, same as its file."""
        doc_key = "integration/cleanup/thumb_dead_doc.pdf"
        thumb_key = "integration/cleanup/thumb_dead_doc/thumbnails/thumb.png"
        live_storage.upload_file(io.BytesIO(b"doc content"), doc_key, "application/pdf")
        live_storage.upload_file(io.BytesIO(b"thumb bytes"), thumb_key, "image/png")

        doc = DocumentFactory(storage_path=doc_key, thumbnail_key=thumb_key)
        doc.soft_delete()

        result = cleanup_service.delete_orphan_blobs(grace_hours=0)

        assert result["deleted"] >= 2
        from botocore.exceptions import ClientError

        for key in (doc_key, thumb_key):
            with pytest.raises(ClientError) as exc_info:
                live_storage.download_file(key)
            assert exc_info.value.response["Error"]["Code"] in ("NoSuchKey", "404")
