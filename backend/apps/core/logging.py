"""Logging utilities: JSON formatter and request-context filter.

JSONFormatter wraps pythonjsonlogger so every log record is emitted as a
single JSON line — parseable by Papertrail, Datadog, CloudWatch, etc.

RequestContextFilter enriches records with organization_id, user_id, and a
request_id when a request is active (reads thread-local set by
OrganizationTenantMiddleware). Falls back gracefully when running outside of
an HTTP request (management commands, Celery tasks).
"""

import logging
import threading
import uuid

# Thread-local store populated by OrganizationTenantMiddleware (or the filter
# itself as a fallback).
_request_context: threading.local = threading.local()


def set_request_context(
    request_id: str | None = None,
    organization_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Store request context in thread-local storage.

    Called by OrganizationTenantMiddleware on each incoming request so that
    log records emitted during the request lifecycle carry tenant context.
    """
    _request_context.request_id = request_id or str(uuid.uuid4())
    _request_context.organization_id = organization_id
    _request_context.user_id = user_id


def clear_request_context() -> None:
    """Remove request context from thread-local storage (call in middleware teardown)."""
    for attr in ("request_id", "organization_id", "user_id"):
        _request_context.__dict__.pop(attr, None)


class RequestContextFilter(logging.Filter):
    """Inject organization_id, user_id, and request_id into every log record.

    Reads values stored by set_request_context(). Falls back to empty strings
    so downstream formatters always find the fields present.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.organization_id = (
            getattr(_request_context, "organization_id", None) or ""
        )
        record.user_id = getattr(_request_context, "user_id", None) or ""
        record.request_id = getattr(_request_context, "request_id", None) or ""
        return True
