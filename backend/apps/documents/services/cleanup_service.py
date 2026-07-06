import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.documents.models import Document, DocumentVersion
from apps.documents.storage.storage_service import StorageService

logger = logging.getLogger(__name__)


def delete_orphan_blobs(grace_hours: int | None = None) -> dict:
    """Delete blobs in the bucket not referenced by any live Document or DocumentVersion.

    System-wide maintenance: deliberately tenant-agnostic (no request, no organization)
    — the only justified exception to the multi-tenancy rule. This is a system-level GC
    job, not a domain operation: the storage bucket is global and blob keys already embed
    the org prefix; there is no safe per-tenant boundary to enforce here.
    Returns a summary dict for logging.

    A blob is kept if EITHER:
      - it is referenced by a live Document.storage_path, OR
      - it is referenced by a DocumentVersion.storage_path whose parent Document is
        alive, OR
      - it is referenced by a live Document.thumbnail_key, OR
      - it was modified less than grace_hours ago (upload-in-flight guard).
    """
    grace = grace_hours if grace_hours is not None else settings.ORPHAN_BLOB_GRACE_HOURS
    cutoff = timezone.now() - timedelta(hours=grace)

    # Source of truth: DB. Build the live-path set in memory.
    # Note: at portfolio scale this is trivial. For millions of blobs the improvement
    # would be scanning by {org_id}/ prefix per tenant.
    live_paths: set[str] = set(Document.objects.values_list("storage_path", flat=True))
    live_paths.update(
        DocumentVersion.objects.filter(document__deleted_at__isnull=True).values_list(
            "storage_path", flat=True
        )
    )
    live_paths.update(
        Document.objects.exclude(thumbnail_key="").values_list(
            "thumbnail_key", flat=True
        )
    )
    live_paths.discard("")  # guard: never treat empty path as a match

    storage = StorageService()
    scanned = deleted = skipped_grace = 0
    for key, last_modified in storage.list_objects():
        scanned += 1
        if key in live_paths:
            continue
        if last_modified > cutoff:
            skipped_grace += 1
            continue
        storage.delete_file(key)
        deleted += 1

    summary = {"scanned": scanned, "deleted": deleted, "skipped_grace": skipped_grace}
    logger.info("cleanup_orphan_blobs: %s", summary)
    return summary
