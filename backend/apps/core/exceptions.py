import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base exception for all SasVault business logic errors."""

    default_code = "ERROR"
    default_message = "An unexpected error occurred"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str | None = None, code: str | None = None) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        super().__init__(self.message)


class PermissionDenied(ApplicationError):
    default_code = "PERMISSION_DENIED"
    default_message = "You do not have permission to perform this action"
    status_code = status.HTTP_403_FORBIDDEN


class NotFound(ApplicationError):
    default_code = "NOT_FOUND"
    default_message = "The requested resource was not found"
    status_code = status.HTTP_404_NOT_FOUND


class ValidationError(ApplicationError):
    default_code = "VALIDATION_ERROR"
    default_message = "Validation failed"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, code)
        self.details = details or {}


class ConflictError(ApplicationError):
    default_code = "CONFLICT"
    default_message = "A conflict occurred with the current state of the resource"
    status_code = status.HTTP_409_CONFLICT


class AIServiceUnavailableError(ApplicationError):
    default_code = "AI_SERVICE_UNAVAILABLE"
    default_message = (
        "AI analysis is not available. Configure ANTHROPIC_API_KEY to enable it."
    )
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class TransientError(Exception):
    """Recoverable failure that should trigger a Celery task retry.

    Deliberately NOT an ApplicationError: it never reaches the HTTP layer. It is
    an internal signal for the retry policy of async tasks — raise it for failures
    that are likely to succeed on a later attempt (e.g. a storage/network timeout),
    as opposed to permanent failures (corrupt file, missing record) which should
    propagate without retrying.
    """


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Transforms all exceptions into the standard API error envelope:
    {"error": {"code": "...", "message": "...", "details": {}}}
    """
    if isinstance(exc, ApplicationError):
        details = getattr(exc, "details", {})
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "details": details}},
            status=exc.status_code,
        )

    # Let DRF handle its own exceptions first, then reformat the response
    response = exception_handler(exc, context)

    if response is not None:
        detail = (
            response.data.get("detail") if isinstance(response.data, dict) else None
        )

        if detail is not None:
            code = getattr(detail, "code", "error").upper().replace(" ", "_")
            message = str(detail)
            details = {}
        else:
            code = "VALIDATION_ERROR"
            message = "Validation failed"
            details = response.data

        response.data = {
            "error": {"code": code, "message": message, "details": details}
        }

    return response
