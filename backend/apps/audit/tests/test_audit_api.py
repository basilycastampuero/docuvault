import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditAction
from apps.audit.tests.factories import AuditLogFactory
from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory

LIST_URL = "/api/v1/audit-logs/"
LOGIN_URL = "/api/v1/auth/login/"


def _login(client: APIClient, user) -> None:
    response = client.post(LOGIN_URL, {"email": user.email, "password": "testpass123"})
    token = response.data["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _client_for(user) -> APIClient:
    client = APIClient()
    _login(client, user)
    return client


def _auditor(org):
    return UserFactory(organization=org, role=UserRole.AUDITOR)


def _org_admin(org):
    return UserFactory(organization=org, role=UserRole.ORG_ADMIN)


def _editor(org):
    return UserFactory(organization=org, role=UserRole.EDITOR)


def _viewer(org):
    return UserFactory(organization=org, role=UserRole.VIEWER)


@pytest.mark.django_db
class TestAuditLogList:
    def test_auditor_can_list(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user, action=AuditAction.CREATE)
        response = _client_for(user).get(LIST_URL)
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "meta" in body
        assert body["meta"]["count"] == 1

    def test_org_admin_can_list(self):
        org = OrganizationFactory()
        user = _org_admin(org)
        AuditLogFactory(organization=org, user=user)
        assert _client_for(user).get(LIST_URL).status_code == 200

    def test_editor_is_forbidden(self):
        org = OrganizationFactory()
        user = _editor(org)
        assert _client_for(user).get(LIST_URL).status_code == 403

    def test_viewer_is_forbidden(self):
        org = OrganizationFactory()
        user = _viewer(org)
        assert _client_for(user).get(LIST_URL).status_code == 403

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(LIST_URL).status_code == 401

    def test_tenant_isolation(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = _auditor(org_a)
        user_b = _auditor(org_b)
        AuditLogFactory(organization=org_a, user=user_a)
        AuditLogFactory(organization=org_a, user=user_a)
        AuditLogFactory(organization=org_b, user=user_b)

        response = _client_for(user_a).get(LIST_URL)
        assert response.json()["meta"]["count"] == 2

    def test_filter_by_action(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user, action=AuditAction.CREATE)
        AuditLogFactory(organization=org, user=user, action=AuditAction.DELETE)

        response = _client_for(user).get(LIST_URL, {"action": "create"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["action"] == "create"

    def test_filter_by_entity_type(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user, entity_type="document")
        AuditLogFactory(organization=org, user=user, entity_type="folder")

        response = _client_for(user).get(LIST_URL, {"entity_type": "document"})
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["entity_type"] == "document"

    def test_filter_by_entity_id(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user, entity_id="target-id")
        AuditLogFactory(organization=org, user=user, entity_id="other-id")

        response = _client_for(user).get(LIST_URL, {"entity_id": "target-id"})
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["entity_id"] == "target-id"

    def test_filter_by_user(self):
        org = OrganizationFactory()
        auditor = _auditor(org)
        other_user = UserFactory(organization=org, role=UserRole.EDITOR)
        AuditLogFactory(organization=org, user=auditor)
        AuditLogFactory(organization=org, user=other_user)

        response = _client_for(auditor).get(LIST_URL, {"user": str(auditor.id)})
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["user"]["id"] == str(auditor.id)

    def test_filter_by_created_after(self):
        org = OrganizationFactory()
        user = _auditor(org)
        old = AuditLogFactory(organization=org, user=user)
        new = AuditLogFactory(organization=org, user=user)

        cutoff = old.created_at.isoformat()
        response = _client_for(user).get(LIST_URL, {"created_after": cutoff})
        ids = [e["id"] for e in response.json()["data"]]
        assert new.id in ids

    def test_filter_by_created_before(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user)
        AuditLogFactory(organization=org, user=user)

        future = "2099-01-01T00:00:00Z"
        response = _client_for(user).get(LIST_URL, {"created_before": future})
        assert response.json()["meta"]["count"] == 2

    def test_post_not_allowed(self):
        org = OrganizationFactory()
        user = _auditor(org)
        assert _client_for(user).post(LIST_URL, {}).status_code == 405

    def test_patch_not_allowed(self):
        org = OrganizationFactory()
        user = _auditor(org)
        AuditLogFactory(organization=org, user=user)
        assert _client_for(user).patch(LIST_URL, {}).status_code == 405


@pytest.mark.django_db
class TestAuditLogDetail:
    def test_auditor_can_retrieve(self):
        org = OrganizationFactory()
        user = _auditor(org)
        entry = AuditLogFactory(organization=org, user=user)

        response = _client_for(user).get(f"{LIST_URL}{entry.id}/")
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert body["data"]["id"] == entry.id

    def test_editor_is_forbidden(self):
        org = OrganizationFactory()
        editor = _editor(org)
        entry = AuditLogFactory(
            organization=org,
            user=UserFactory(organization=org, role=UserRole.AUDITOR),
        )
        assert _client_for(editor).get(f"{LIST_URL}{entry.id}/").status_code == 403

    def test_tenant_isolation_returns_404(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = UserFactory(organization=org_a, role=UserRole.AUDITOR)
        user_b = UserFactory(organization=org_b, role=UserRole.AUDITOR)
        entry_a = AuditLogFactory(organization=org_a, user=user_a)

        response = _client_for(user_b).get(f"{LIST_URL}{entry_a.id}/")
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self):
        org = OrganizationFactory()
        user = _auditor(org)
        entry = AuditLogFactory(organization=org, user=user)
        assert APIClient().get(f"{LIST_URL}{entry.id}/").status_code == 401

    def test_delete_not_allowed(self):
        org = OrganizationFactory()
        user = _auditor(org)
        entry = AuditLogFactory(organization=org, user=user)
        assert _client_for(user).delete(f"{LIST_URL}{entry.id}/").status_code == 405
