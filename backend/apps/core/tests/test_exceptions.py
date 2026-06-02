from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.test import APIRequestFactory

from apps.core.exceptions import (
    ApplicationError,
    ConflictError,
    NotFound,
    PermissionDenied,
    TransientError,
    ValidationError,
    custom_exception_handler,
)


class TestApplicationError:
    def test_default_code_and_message(self):
        exc = ApplicationError()
        assert exc.code == "ERROR"
        assert exc.message == "An unexpected error occurred"
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_custom_code_and_message(self):
        exc = ApplicationError(message="custom msg", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"
        assert exc.message == "custom msg"

    def test_is_exception_subclass(self):
        assert issubclass(ApplicationError, Exception)


class TestBusinessExceptions:
    def test_permission_denied_defaults(self):
        exc = PermissionDenied()
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.code == "PERMISSION_DENIED"

    def test_not_found_defaults(self):
        exc = NotFound()
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.code == "NOT_FOUND"

    def test_validation_error_defaults(self):
        exc = ValidationError()
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.code == "VALIDATION_ERROR"
        assert exc.details == {}

    def test_validation_error_with_details(self):
        exc = ValidationError(details={"email": ["This field is required."]})
        assert exc.details == {"email": ["This field is required."]}

    def test_conflict_error_defaults(self):
        exc = ConflictError()
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.code == "CONFLICT"


class TestTransientError:
    def test_is_exception_but_not_application_error(self):
        # It must stay outside the HTTP error family: it is an internal retry signal.
        assert issubclass(TransientError, Exception)
        assert not issubclass(TransientError, ApplicationError)

    def test_handler_ignores_transient_error(self):
        factory = APIRequestFactory()
        context = {"request": factory.get("/"), "view": None}
        assert custom_exception_handler(TransientError("timeout"), context) is None


class TestCustomExceptionHandler:
    def _get_context(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        return {"request": request, "view": None}

    def test_application_error_returns_error_envelope(self):
        exc = ApplicationError(message="something went wrong", code="BOOM")
        response = custom_exception_handler(exc, self._get_context())

        assert response is not None
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "BOOM"
        assert response.data["error"]["message"] == "something went wrong"
        assert "details" in response.data["error"]

    def test_permission_denied_returns_403(self):
        exc = PermissionDenied()
        response = custom_exception_handler(exc, self._get_context())

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "PERMISSION_DENIED"

    def test_not_found_returns_404(self):
        exc = NotFound(message="Document not found")
        response = custom_exception_handler(exc, self._get_context())

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["message"] == "Document not found"

    def test_validation_error_includes_details(self):
        exc = ValidationError(details={"name": ["This field is required."]})
        response = custom_exception_handler(exc, self._get_context())

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["details"] == {
            "name": ["This field is required."]
        }

    def test_drf_not_authenticated_returns_envelope(self):
        exc = NotAuthenticated()
        response = custom_exception_handler(exc, self._get_context())

        assert response is not None
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "code" in response.data["error"]
        assert "message" in response.data["error"]

    def test_drf_permission_denied_returns_envelope(self):
        exc = DRFPermissionDenied()
        response = custom_exception_handler(exc, self._get_context())

        assert response is not None
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "error" in response.data

    def test_unhandled_exception_returns_none(self):
        exc = KeyError("unexpected")
        response = custom_exception_handler(exc, self._get_context())

        assert response is None
