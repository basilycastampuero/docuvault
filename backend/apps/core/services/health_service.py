import logging

logger = logging.getLogger(__name__)


def check_health() -> dict:
    """System-wide connectivity check (db, redis, storage).

    Tenant-agnostic: no request, no organization. Runs before/without auth.
    Returns a dict with keys "database", "redis", "storage", each "ok" or "error".
    Never raises.
    """
    return {
        "database": _check_database(),
        "redis": _check_redis(),
        "storage": _check_storage(),
    }


def _check_database() -> str:
    """Execute a trivial DB query to verify connectivity."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception:
        logger.exception("Health check: database connectivity failed")
        return "error"


def _check_redis() -> str:
    """Ping Redis using Django's cache backend."""
    from django.core.cache import cache

    try:
        cache.set("health_check", "1", timeout=5)
        return "ok" if cache.get("health_check") == "1" else "error"
    except Exception:
        logger.exception("Health check: Redis connectivity failed")
        return "error"


def _check_storage() -> str:
    """Verify MinIO/S3 bucket exists and is accessible."""
    from apps.documents.storage.storage_service import StorageService

    try:
        storage = StorageService()
        storage.ensure_bucket()
        return "ok"
    except Exception:
        logger.exception("Health check: object storage connectivity failed")
        return "error"
