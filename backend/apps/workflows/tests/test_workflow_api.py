import pytest
from rest_framework.test import APIClient

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.models import DocumentStatus
from apps.documents.tests.factories import DocumentFactory
from apps.organizations.tests.factories import OrganizationFactory

LOGIN_URL = "/api/v1/auth/login/"
TEMPLATES_URL = "/api/v1/workflows/templates/"
EXECUTIONS_URL = "/api/v1/workflows/executions/"

_STEPS = [
    {
        "name": "Review",
        "order": 1,
        "required_role": UserRole.SUPERVISOR,
        "is_final": False,
    },
    {
        "name": "Approve",
        "order": 2,
        "required_role": UserRole.ORG_ADMIN,
        "is_final": True,
    },
]


def _login(client: APIClient, user) -> None:
    response = client.post(LOGIN_URL, {"email": user.email, "password": "testpass123"})
    token = response.data["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _client_for(user) -> APIClient:
    client = APIClient()
    _login(client, user)
    return client


def _admin(org):
    return UserFactory(organization=org, role=UserRole.ORG_ADMIN)


@pytest.mark.django_db
class TestTemplateAPI:
    def test_admin_can_create_template(self):
        org = OrganizationFactory()
        admin = _admin(org)
        response = _client_for(admin).post(
            TEMPLATES_URL,
            {"name": "Approval", "steps": _STEPS},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["name"] == "Approval"
        assert len(body["data"]["steps"]) == 2

    def test_editor_cannot_create_template(self):
        org = OrganizationFactory()
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        response = _client_for(editor).post(
            TEMPLATES_URL, {"name": "X", "steps": _STEPS}, format="json"
        )
        assert response.status_code == 403

    def test_any_member_can_list_templates(self):
        org = OrganizationFactory()
        viewer = UserFactory(organization=org, role=UserRole.VIEWER)
        response = _client_for(viewer).get(TEMPLATES_URL)
        assert response.status_code == 200
        assert "data" in response.json()

    def test_unauthenticated_returns_401(self):
        assert APIClient().get(TEMPLATES_URL).status_code == 401

    def test_create_without_final_step_returns_400(self):
        org = OrganizationFactory()
        admin = _admin(org)
        bad_steps = [
            {
                "name": "Only",
                "order": 1,
                "required_role": UserRole.SUPERVISOR,
                "is_final": False,
            }
        ]
        response = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Bad", "steps": bad_steps}, format="json"
        )
        assert response.status_code == 400

    def test_admin_can_update_template(self):
        org = OrganizationFactory()
        admin = _admin(org)
        created = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Approval", "steps": _STEPS}, format="json"
        )
        template_id = created.json()["data"]["id"]

        response = _client_for(admin).patch(
            f"{TEMPLATES_URL}{template_id}/",
            {"is_active": False, "name": "Renamed"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_active"] is False
        assert response.json()["data"]["name"] == "Renamed"

    def test_editor_cannot_update_template(self):
        org = OrganizationFactory()
        admin = _admin(org)
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        created = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Approval", "steps": _STEPS}, format="json"
        )
        template_id = created.json()["data"]["id"]

        response = _client_for(editor).patch(
            f"{TEMPLATES_URL}{template_id}/", {"is_active": False}, format="json"
        )
        assert response.status_code == 403

    def test_admin_can_delete_template(self):
        org = OrganizationFactory()
        admin = _admin(org)
        created = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Approval", "steps": _STEPS}, format="json"
        )
        template_id = created.json()["data"]["id"]

        response = _client_for(admin).delete(f"{TEMPLATES_URL}{template_id}/")
        assert response.status_code == 204

    def test_retrieve_template(self):
        org = OrganizationFactory()
        admin = _admin(org)
        created = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Approval", "steps": _STEPS}, format="json"
        )
        template_id = created.json()["data"]["id"]

        response = _client_for(admin).get(f"{TEMPLATES_URL}{template_id}/")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == template_id


@pytest.mark.django_db
class TestExecutionAPI:
    def _create_template(self, admin) -> str:
        response = _client_for(admin).post(
            TEMPLATES_URL, {"name": "Approval", "steps": _STEPS}, format="json"
        )
        return response.json()["data"]["id"]

    def test_full_flow_start_advance_complete(self):
        org = OrganizationFactory()
        admin = _admin(org)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template_id = self._create_template(admin)
        document = DocumentFactory(organization=org, created_by=admin)

        # start
        start = _client_for(admin).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )
        assert start.status_code == 201
        execution_id = start.json()["data"]["id"]
        assert start.json()["data"]["status"] == "in_progress"

        # supervisor approves step 1
        advance_url = f"{EXECUTIONS_URL}{execution_id}/advance/"
        step1 = _client_for(supervisor).post(
            advance_url, {"action": "approved"}, format="json"
        )
        assert step1.status_code == 200
        assert step1.json()["data"]["current_step"]["order"] == 2

        # admin approves final step
        step2 = _client_for(admin).post(
            advance_url, {"action": "approved"}, format="json"
        )
        assert step2.status_code == 200
        assert step2.json()["data"]["status"] == "completed"

        document.refresh_from_db()
        assert document.status == DocumentStatus.APPROVED

    def test_advance_with_wrong_role_returns_403(self):
        org = OrganizationFactory()
        admin = _admin(org)
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        template_id = self._create_template(admin)
        document = DocumentFactory(organization=org, created_by=admin)
        start = _client_for(admin).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )
        execution_id = start.json()["data"]["id"]

        response = _client_for(editor).post(
            f"{EXECUTIONS_URL}{execution_id}/advance/",
            {"action": "approved"},
            format="json",
        )
        assert response.status_code == 403

    def test_viewer_cannot_start_workflow(self):
        org = OrganizationFactory()
        admin = _admin(org)
        viewer = UserFactory(organization=org, role=UserRole.VIEWER)
        template_id = self._create_template(admin)
        document = DocumentFactory(organization=org, created_by=admin)

        response = _client_for(viewer).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )
        assert response.status_code == 403

    def test_execution_logs_endpoint(self):
        org = OrganizationFactory()
        admin = _admin(org)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template_id = self._create_template(admin)
        document = DocumentFactory(organization=org, created_by=admin)
        start = _client_for(admin).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )
        execution_id = start.json()["data"]["id"]
        _client_for(supervisor).post(
            f"{EXECUTIONS_URL}{execution_id}/advance/",
            {"action": "commented", "comment": "noted"},
            format="json",
        )

        logs = _client_for(admin).get(f"{EXECUTIONS_URL}{execution_id}/logs/")
        assert logs.status_code == 200
        data = logs.json()["data"]
        assert len(data) == 1
        assert data[0]["action"] == "commented"

    def test_list_executions_with_status_filter(self):
        org = OrganizationFactory()
        admin = _admin(org)
        template_id = self._create_template(admin)
        document = DocumentFactory(organization=org, created_by=admin)
        _client_for(admin).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )

        response = _client_for(admin).get(EXECUTIONS_URL, {"status": "in_progress"})
        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["count"] == 1
        assert body["data"][0]["status"] == "in_progress"

    def test_execution_tenant_isolation(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        admin_a = _admin(org_a)
        admin_b = _admin(org_b)
        template_id = self._create_template(admin_a)
        document = DocumentFactory(organization=org_a, created_by=admin_a)
        start = _client_for(admin_a).post(
            EXECUTIONS_URL,
            {"document_id": str(document.id), "template_id": template_id},
            format="json",
        )
        execution_id = start.json()["data"]["id"]

        response = _client_for(admin_b).get(f"{EXECUTIONS_URL}{execution_id}/")
        assert response.status_code == 404
