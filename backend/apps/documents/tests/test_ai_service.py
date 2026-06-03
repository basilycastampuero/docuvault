"""Tests for ai_service.analyze().

The Anthropic client is always mocked — no real API calls are made.
"""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.audit.models import AuditLog
from apps.core.exceptions import (
    AIServiceUnavailableError,
    ConflictError,
    TransientError,
)
from apps.documents.services import ai_service

from .factories import DocumentFactory


def _make_response(text: str):
    """Return a minimal mock that mimics anthropic.types.Message."""
    block = SimpleNamespace(text=text)
    return SimpleNamespace(content=[block])


@contextmanager
def _mock_anthropic_ctx(response_text: str):
    """Context manager that patches anthropic.Anthropic (imported locally in analyze()).

    Because ``import anthropic`` is a local statement inside ``analyze()``,
    the name is resolved from ``sys.modules`` at call time. Patching
    ``anthropic.Anthropic`` (the class on the real module) is the reliable way
    to intercept it without touching module-level attributes.
    """
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(response_text)
    with patch("anthropic.Anthropic", return_value=mock_client):
        yield mock_client


def _mock_anthropic(monkeypatch, response_text: str) -> MagicMock:
    """Patch anthropic.Anthropic and return the mock client (non-context-manager form)."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_response(response_text)
    monkeypatch.setattr("anthropic.Anthropic", MagicMock(return_value=mock_client))
    return mock_client


_VALID_RESPONSE = json.dumps(
    {
        "summary": "A quarterly report.",
        "entities": {
            "dates": ["2026-01-01"],
            "amounts": ["$1,000"],
            "names": ["Acme Corp"],
        },
        "suggested_category": "Finance",
    }
)


@pytest.mark.django_db
class TestAiServiceAnalyze:
    def test_happy_path_returns_analysis_dict(self, monkeypatch, settings):
        """analyze() returns a dict with expected keys and persists to metadata."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Quarterly report for Acme Corp Q1 2026.")
        mock_client = _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        result = ai_service.analyze(doc)

        assert result["summary"] == "A quarterly report."
        assert result["entities"]["dates"] == ["2026-01-01"]
        assert result["entities"]["amounts"] == ["$1,000"]
        assert result["entities"]["names"] == ["Acme Corp"]
        assert result["suggested_category"] == "Finance"
        assert "ai_analysis_at" in result
        mock_client.messages.create.assert_called_once()

    def test_happy_path_persists_to_metadata(self, monkeypatch, settings):
        """analyze() saves result inside document.metadata['ai_analysis']."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some OCR text here.")
        _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        doc.refresh_from_db()
        assert "ai_analysis" in doc.metadata
        assert doc.metadata["ai_analysis"]["summary"] == "A quarterly report."
        assert "ai_analysis_at" in doc.metadata["ai_analysis"]

    def test_happy_path_creates_audit_log(self, monkeypatch, settings):
        """analyze() logs an UPDATE audit event with via=ai_analysis."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some text.")
        _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        log = AuditLog.objects.filter(
            entity_type="document",
            entity_id=str(doc.pk),
        ).last()
        assert log is not None
        assert log.metadata == {"via": "ai_analysis"}

    def test_missing_key_raises_503(self, settings):
        """When ANTHROPIC_API_KEY is empty the feature is off → AIServiceUnavailableError."""
        settings.ANTHROPIC_API_KEY = ""
        doc = DocumentFactory(ocr_content="Some text.")

        with pytest.raises(AIServiceUnavailableError):
            ai_service.analyze(doc)

    def test_empty_ocr_content_raises_conflict(self, settings):
        """analyze() raises ConflictError(code='AI_NO_CONTENT') for empty ocr_content."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="")

        with pytest.raises(ConflictError) as exc_info:
            ai_service.analyze(doc)

        assert exc_info.value.code == "AI_NO_CONTENT"

    def test_whitespace_only_ocr_content_raises_conflict(self, settings):
        """analyze() raises ConflictError when ocr_content is only whitespace."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="   \n\t  ")

        with pytest.raises(ConflictError) as exc_info:
            ai_service.analyze(doc)

        assert exc_info.value.code == "AI_NO_CONTENT"

    def test_malformed_response_raises_transient_error(self, monkeypatch, settings):
        """A non-JSON model response raises TransientError (triggers Celery retry)."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some text.")
        _mock_anthropic(monkeypatch, "this is not valid JSON!!!")

        with pytest.raises(TransientError):
            ai_service.analyze(doc)

    def test_input_truncated_to_ai_max_input_chars(self, monkeypatch, settings):
        """Long ocr_content is truncated to AI_MAX_INPUT_CHARS before sending."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        settings.AI_MAX_INPUT_CHARS = 100
        doc = DocumentFactory(ocr_content="x" * 500)
        mock_client = _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        call_kwargs = mock_client.messages.create.call_args
        user_message = call_kwargs.kwargs["messages"][0]["content"]
        assert len(user_message) == 100

    def test_system_prompt_has_cache_control_ephemeral(self, monkeypatch, settings):
        """The system array sent to the API carries cache_control=ephemeral."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some text.")
        mock_client = _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        call_kwargs = mock_client.messages.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        assert isinstance(system_blocks, list)
        assert len(system_blocks) == 1
        assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_metadata_save_does_not_modify_search_vector(self, monkeypatch, settings):
        """Saving metadata leaves search_vector unchanged (FTS signal skips rebuild)."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some text.")
        # Force the search_vector to be built first
        doc.refresh_from_db()
        vector_before = doc.search_vector
        _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        doc.refresh_from_db()
        assert doc.search_vector == vector_before

    def test_audit_log_has_correct_organization(self, monkeypatch, settings):
        """AuditLog created by analyze() belongs to the document's organization."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        doc = DocumentFactory(ocr_content="Some text.")
        _mock_anthropic(monkeypatch, _VALID_RESPONSE)

        ai_service.analyze(doc)

        log = AuditLog.objects.filter(entity_id=str(doc.pk)).last()
        assert log.organization_id == doc.organization_id
