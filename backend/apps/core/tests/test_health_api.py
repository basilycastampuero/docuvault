"""Tests for GET /api/v1/health/ (HealthCheckView).

Key invariants verified:
- 200 when all components healthy, 503 when any component is degraded
- Flat JSON shape (no {data, meta} envelope) — deliberate exception to standard
- Fully public: no JWT required, no tenant middleware header required
- Never generates an AuditLog entry
"""

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.core.services import health_service

HEALTH_URL = "/api/v1/health/"


def _all_ok_patch(monkeypatch) -> None:
    """Patch all three checkers to return 'ok'."""
    monkeypatch.setattr(health_service, "_check_database", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_redis", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_storage", lambda: "ok")


def _one_down_patch(monkeypatch) -> None:
    """Patch storage checker to simulate a degraded component."""
    monkeypatch.setattr(health_service, "_check_database", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_redis", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_storage", lambda: "error")


class TestHealthCheckView:
    """Functional tests for HealthCheckView."""

    # ------------------------------------------------------------------ #
    # Status codes                                                         #
    # ------------------------------------------------------------------ #

    def test_healthy_returns_200(self, monkeypatch):
        """Should return HTTP 200 when all infrastructure components are healthy."""
        _all_ok_patch(monkeypatch)
        response = APIClient().get(HEALTH_URL)
        assert response.status_code == 200

    def test_degraded_returns_503(self, monkeypatch):
        """Should return HTTP 503 when at least one component reports an error."""
        _one_down_patch(monkeypatch)
        response = APIClient().get(HEALTH_URL)
        assert response.status_code == 503

    def test_all_components_down_returns_503(self, monkeypatch):
        """Should return HTTP 503 when every component fails."""
        monkeypatch.setattr(health_service, "_check_database", lambda: "error")
        monkeypatch.setattr(health_service, "_check_redis", lambda: "error")
        monkeypatch.setattr(health_service, "_check_storage", lambda: "error")
        response = APIClient().get(HEALTH_URL)
        assert response.status_code == 503

    # ------------------------------------------------------------------ #
    # Response shape                                                       #
    # ------------------------------------------------------------------ #

    def test_response_shape_has_status_and_components(self, monkeypatch):
        """Should include exactly 'status' and 'components' at the top level."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert set(body.keys()) == {"status", "components"}

    def test_response_components_has_all_three_keys(self, monkeypatch):
        """Should include 'database', 'redis', and 'storage' under 'components'."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert set(body["components"].keys()) == {"database", "redis", "storage"}

    def test_healthy_status_field_is_ok(self, monkeypatch):
        """Should report status='ok' in the body when all components pass."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert body["status"] == "ok"

    def test_degraded_status_field_is_degraded(self, monkeypatch):
        """Should report status='degraded' in the body when a component fails."""
        _one_down_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert body["status"] == "degraded"

    def test_component_values_are_ok_when_healthy(self, monkeypatch):
        """Should report 'ok' for every component when all checkers succeed."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert body["components"]["database"] == "ok"
        assert body["components"]["redis"] == "ok"
        assert body["components"]["storage"] == "ok"

    def test_failing_component_reported_as_error(self, monkeypatch):
        """Should report individual failing component as 'error'."""
        _one_down_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert body["components"]["storage"] == "error"
        # Healthy components must still read 'ok'
        assert body["components"]["database"] == "ok"
        assert body["components"]["redis"] == "ok"

    # ------------------------------------------------------------------ #
    # No envelope — deliberate exception to {data, meta} standard         #
    # ------------------------------------------------------------------ #

    def test_no_envelope_data_key_absent(self, monkeypatch):
        """Should NOT wrap the response in the standard {data, meta} envelope."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert "data" not in body

    def test_no_envelope_meta_key_absent(self, monkeypatch):
        """Should NOT include a 'meta' key — health response is flat JSON."""
        _all_ok_patch(monkeypatch)
        body = APIClient().get(HEALTH_URL).json()
        assert "meta" not in body

    # ------------------------------------------------------------------ #
    # Authentication — endpoint must be fully public                      #
    # ------------------------------------------------------------------ #

    def test_no_auth_required_anonymous_gets_200(self, monkeypatch):
        """Should return 200 without a JWT — endpoint is truly public."""
        _all_ok_patch(monkeypatch)
        client = APIClient()
        # Explicitly ensure no credentials are set
        client.credentials()
        response = client.get(HEALTH_URL)
        assert response.status_code == 200

    def test_no_auth_required_invalid_token_still_succeeds(self, monkeypatch):
        """Should return 200 even with a malformed Authorization header."""
        _all_ok_patch(monkeypatch)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer totally-invalid-token")
        response = client.get(HEALTH_URL)
        # authentication_classes=[] means DRF never tries to parse the token
        assert response.status_code == 200

    # ------------------------------------------------------------------ #
    # Tenant middleware — must not fail without organization context       #
    # ------------------------------------------------------------------ #

    def test_no_organization_header_does_not_error(self, monkeypatch):
        """Should succeed without a tenant organization header (no middleware crash)."""
        _all_ok_patch(monkeypatch)
        client = APIClient()
        # Deliberately omit any organization-related header
        response = client.get(HEALTH_URL)
        assert response.status_code == 200

    # ------------------------------------------------------------------ #
    # Audit log — health check must not be audited                        #
    # ------------------------------------------------------------------ #

    @pytest.mark.django_db
    def test_not_audited_no_audit_log_created(self, monkeypatch):
        """Should NOT generate any AuditLog row when the health endpoint is called."""
        _all_ok_patch(monkeypatch)
        count_before = AuditLog.objects.count()
        APIClient().get(HEALTH_URL)
        count_after = AuditLog.objects.count()
        assert count_after == count_before

    @pytest.mark.django_db
    def test_not_audited_even_when_degraded(self, monkeypatch):
        """Should NOT generate any AuditLog row even when a component is degraded."""
        _one_down_patch(monkeypatch)
        count_before = AuditLog.objects.count()
        APIClient().get(HEALTH_URL)
        count_after = AuditLog.objects.count()
        assert count_after == count_before

    # ------------------------------------------------------------------ #
    # HTTP method — only GET is supported                                  #
    # ------------------------------------------------------------------ #

    def test_post_method_not_allowed(self, monkeypatch):
        """Should return 405 for POST — endpoint is read-only."""
        _all_ok_patch(monkeypatch)
        response = APIClient().post(HEALTH_URL, {}, format="json")
        assert response.status_code == 405

    def test_delete_method_not_allowed(self, monkeypatch):
        """Should return 405 for DELETE — endpoint is read-only."""
        _all_ok_patch(monkeypatch)
        response = APIClient().delete(HEALTH_URL)
        assert response.status_code == 405
