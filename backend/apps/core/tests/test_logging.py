"""Tests for apps.core.logging (RequestContextFilter, set/clear helpers).

Thread-local state is explicitly reset before each test so that test
ordering never affects results.
"""

import logging

import pytest

from apps.core.logging import (
    RequestContextFilter,
    _request_context,
    clear_request_context,
    set_request_context,
)


def _make_record(message: str = "test message") -> logging.LogRecord:
    """Return a bare LogRecord suitable for passing to filter()."""
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )


@pytest.fixture(autouse=True)
def _clean_thread_local():
    """Guarantee clean thread-local state before and after every test."""
    clear_request_context()
    yield
    clear_request_context()


class TestRequestContextFilter:
    """Tests for RequestContextFilter.filter()."""

    def test_filter_adds_organization_id_when_context_set(self):
        """Should inject organization_id from thread-local into the log record."""
        set_request_context(organization_id="org-abc-123")
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.organization_id == "org-abc-123"

    def test_filter_adds_user_id_when_context_set(self):
        """Should inject user_id from thread-local into the log record."""
        set_request_context(user_id="user-xyz-456")
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.user_id == "user-xyz-456"

    def test_filter_adds_request_id_when_context_set(self):
        """Should inject request_id from thread-local into the log record."""
        set_request_context(request_id="req-001")
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.request_id == "req-001"

    def test_filter_adds_all_three_fields_simultaneously(self):
        """Should inject all three context fields in a single filter() call."""
        set_request_context(
            request_id="req-999",
            organization_id="org-999",
            user_id="usr-999",
        )
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.request_id == "req-999"
        assert record.organization_id == "org-999"
        assert record.user_id == "usr-999"

    def test_filter_returns_true(self):
        """Should return True (allow all records to pass through)."""
        set_request_context(organization_id="any-org")
        record = _make_record()
        result = RequestContextFilter().filter(record)
        assert result is True

    def test_filter_empty_when_no_context_organization_id(self):
        """Should set organization_id to empty string when no context is active."""
        # thread-local is clear thanks to autouse fixture
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.organization_id == ""

    def test_filter_empty_when_no_context_user_id(self):
        """Should set user_id to empty string when no context is active."""
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.user_id == ""

    def test_filter_empty_when_no_context_request_id(self):
        """Should set request_id to empty string when no context is active."""
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.request_id == ""

    def test_filter_does_not_raise_without_context(self):
        """Should never raise KeyError or AttributeError when thread-local is empty."""
        record = _make_record()
        # Must not raise under any circumstances
        RequestContextFilter().filter(record)

    def test_filter_handles_none_values_as_empty_string(self):
        """Should normalise None values to empty string in log records."""
        set_request_context(
            request_id="req-001",
            organization_id=None,
            user_id=None,
        )
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.organization_id == ""
        assert record.user_id == ""

    def test_filter_after_clear_returns_empty_fields(self):
        """Should produce empty fields after clear_request_context() is called."""
        set_request_context(organization_id="org-before", user_id="usr-before")
        clear_request_context()
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.organization_id == ""
        assert record.user_id == ""
        assert record.request_id == ""


class TestSetRequestContext:
    """Tests for set_request_context()."""

    def test_populates_organization_id(self):
        """Should store organization_id in thread-local after calling set."""
        set_request_context(organization_id="org-set-test")
        assert _request_context.organization_id == "org-set-test"

    def test_populates_user_id(self):
        """Should store user_id in thread-local after calling set."""
        set_request_context(user_id="user-set-test")
        assert _request_context.user_id == "user-set-test"

    def test_populates_request_id_from_argument(self):
        """Should store the given request_id verbatim in thread-local."""
        set_request_context(request_id="explicit-req-id")
        assert _request_context.request_id == "explicit-req-id"

    def test_auto_generates_request_id_when_none_provided(self):
        """Should generate a UUID request_id when none is passed."""
        import uuid

        set_request_context(organization_id="org-uuid-test")
        generated_id = _request_context.request_id
        # Must be a valid UUID4 string
        parsed = uuid.UUID(generated_id, version=4)
        assert str(parsed) == generated_id

    def test_overwrites_previous_context(self):
        """Should replace previously stored context on a subsequent call."""
        set_request_context(organization_id="org-first", user_id="usr-first")
        set_request_context(organization_id="org-second", user_id="usr-second")
        assert _request_context.organization_id == "org-second"
        assert _request_context.user_id == "usr-second"

    def test_allows_none_for_optional_fields(self):
        """Should store None for organization_id and user_id when not provided."""
        set_request_context(request_id="req-only")
        assert _request_context.organization_id is None
        assert _request_context.user_id is None


class TestClearRequestContext:
    """Tests for clear_request_context()."""

    def test_removes_organization_id(self):
        """Should remove organization_id from thread-local after clear."""
        set_request_context(organization_id="org-to-clear")
        clear_request_context()
        assert not hasattr(_request_context, "organization_id")

    def test_removes_user_id(self):
        """Should remove user_id from thread-local after clear."""
        set_request_context(user_id="user-to-clear")
        clear_request_context()
        assert not hasattr(_request_context, "user_id")

    def test_removes_request_id(self):
        """Should remove request_id from thread-local after clear."""
        set_request_context(request_id="req-to-clear")
        clear_request_context()
        assert not hasattr(_request_context, "request_id")

    def test_idempotent_when_already_clear(self):
        """Should not raise when called on already-empty thread-local state."""
        # context is already clear from autouse fixture
        clear_request_context()  # second call must be safe

    def test_filter_returns_empty_after_clear(self):
        """Should cause RequestContextFilter to emit empty fields after clear."""
        set_request_context(organization_id="org-temp", user_id="usr-temp")
        clear_request_context()
        record = _make_record()
        RequestContextFilter().filter(record)
        assert record.organization_id == ""
        assert record.user_id == ""
        assert record.request_id == ""
