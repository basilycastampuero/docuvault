import json
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.core.exceptions import (
    AIServiceUnavailableError,
    ConflictError,
    TransientError,
)

if TYPE_CHECKING:
    from apps.documents.models import Document

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a document information extractor. "
    "Analyze the provided document text and return ONLY valid JSON with exactly "
    'this structure:\n{"summary": "string", "entities": {"dates": ["string"], '
    '"amounts": ["string"], "names": ["string"]}, "suggested_category": "string"}\n'
    "No text outside the JSON. No markdown. No explanation."
)


def analyze(document: "Document") -> dict:
    """Run Claude analysis over a document's OCR content and persist the result
    in document.metadata['ai_analysis']. Returns the analysis dict.

    Feature-flagged: raises AIServiceUnavailableError (503) if ANTHROPIC_API_KEY
    is unset. Raises ConflictError if the document has no OCR content. Raises
    TransientError on a malformed model response so Celery retries.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIServiceUnavailableError()

    content = (document.ocr_content or "").strip()
    if not content:
        raise ConflictError(
            "Document has no OCR content to analyze", code="AI_NO_CONTENT"
        )

    truncated = content[: settings.AI_MAX_INPUT_CHARS]

    # Instantiated inside the function — a missing key must not break imports or
    # tests that do not exercise the AI feature.
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": truncated}],
    )

    analysis = _parse_response(response)
    analysis["ai_analysis_at"] = timezone.now().isoformat()

    # update_fields=["metadata", "updated_at"] does NOT touch name/description/
    # tags/ocr_content, so the FTS signal skips the rebuild — no write amplification.
    document.metadata["ai_analysis"] = analysis
    document.save(update_fields=["metadata", "updated_at"])

    audit_service.log(
        organization=document.organization,
        user=None,
        entity_type="document",
        entity_id=str(document.pk),
        action=AuditAction.UPDATE,
        metadata={"via": "ai_analysis"},
    )
    logger.info("AI analysis completed for %s", document.pk)
    return analysis


def _parse_response(response) -> dict:
    """Parse and normalize Claude's JSON response. Raises TransientError if malformed."""
    try:
        text = response.content[0].text
        data = json.loads(text)
    except (json.JSONDecodeError, IndexError, AttributeError, TypeError) as exc:
        raise TransientError(f"AI returned malformed response: {exc}") from exc

    return {
        "summary": data.get("summary", ""),
        "entities": {
            "dates": data.get("entities", {}).get("dates", []),
            "amounts": data.get("entities", {}).get("amounts", []),
            "names": data.get("entities", {}).get("names", []),
        },
        "suggested_category": data.get("suggested_category", ""),
    }
