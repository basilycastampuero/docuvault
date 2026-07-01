import io
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIClient

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.models import DocumentStatus
from apps.documents.storage.storage_service import StorageService as RealStorageService
from apps.organizations.tests.factories import OrganizationFactory

from .factories import DocumentFactory, DocumentVersionFactory, FolderFactory

PDF_HEADER = b"%PDF-1.4\n" + b"%" * 100
LOGIN_URL = "/api/v1/auth/login/"


def _login(client: APIClient, user) -> None:
    """Authenticate via JWT so the tenant middleware sets request.organization."""
    response = client.post(
        LOGIN_URL,
        {"email": user.email, "password": "testpass123"},
    )
    token = response.data["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def _client_for(user) -> APIClient:
    client = APIClient()
    _login(client, user)
    return client


def _editor(org):
    return UserFactory(organization=org, role=UserRole.EDITOR)


def _viewer(org):
    return UserFactory(organization=org, role=UserRole.VIEWER)


def _storage_mock(monkeypatch) -> MagicMock:
    """Return a mocked StorageService instance, preserving the static method."""
    mock_instance = MagicMock()
    mock_instance.upload_file.return_value = "org/2026/01/doc/file.pdf"
    mock_class = MagicMock()
    mock_class.return_value = mock_instance
    mock_class.build_storage_path = RealStorageService.build_storage_path
    monkeypatch.setattr(
        "apps.documents.services.document_service.StorageService", mock_class
    )
    # transaction=True tests fire on_commit; with CELERY_TASK_ALWAYS_EAGER the
    # OCR task runs synchronously and tries to reach MinIO (unavailable in CI).
    monkeypatch.setattr(
        "apps.documents.services.document_service.process_ocr.delay",
        MagicMock(),
    )
    return mock_instance


# ---------------------------------------------------------------------------
# Folder API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFolderListCreate:
    def test_list_folders_authenticated(self):
        org = OrganizationFactory()
        user = _viewer(org)
        FolderFactory(organization=org, owner=user)
        response = _client_for(user).get("/api/v1/folders/")
        assert response.status_code == 200
        assert "data" in response.json()

    def test_list_folders_unauthenticated(self):
        assert APIClient().get("/api/v1/folders/").status_code == 401

    def test_list_folders_tenant_isolation(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user1 = _viewer(org1)
        user2 = _viewer(org2)
        FolderFactory(organization=org1, owner=user1)
        FolderFactory(organization=org2, owner=user2)
        response = _client_for(user1).get("/api/v1/folders/")
        assert len(response.json()["data"]) == 1

    def test_create_folder_editor(self):
        org = OrganizationFactory()
        user = _editor(org)
        response = _client_for(user).post(
            "/api/v1/folders/", {"name": "Reports"}, format="json"
        )
        assert response.status_code == 201
        assert response.json()["data"]["name"] == "Reports"

    def test_create_folder_viewer_forbidden(self):
        org = OrganizationFactory()
        user = _viewer(org)
        response = _client_for(user).post(
            "/api/v1/folders/", {"name": "X"}, format="json"
        )
        assert response.status_code == 403

    def test_envelope_structure(self):
        org = OrganizationFactory()
        user = _viewer(org)
        FolderFactory(organization=org, owner=user)
        data = _client_for(user).get("/api/v1/folders/").json()
        assert "data" in data
        assert "meta" in data


@pytest.mark.django_db
class TestFolderDetail:
    def test_get_folder(self):
        org = OrganizationFactory()
        user = _viewer(org)
        folder = FolderFactory(organization=org, owner=user)
        response = _client_for(user).get(f"/api/v1/folders/{folder.id}/")
        assert response.status_code == 200
        assert response.json()["data"]["name"] == folder.name

    def test_get_folder_wrong_org_not_found(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = _viewer(org1)
        folder = FolderFactory(organization=org2)
        assert _client_for(user).get(f"/api/v1/folders/{folder.id}/").status_code == 404

    def test_patch_folder_renames(self):
        org = OrganizationFactory()
        user = _editor(org)
        folder = FolderFactory(organization=org, owner=user)
        response = _client_for(user).patch(
            f"/api/v1/folders/{folder.id}/", {"name": "Renamed"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Renamed"

    def test_delete_empty_folder(self):
        org = OrganizationFactory()
        user = _editor(org)
        folder = FolderFactory(organization=org, owner=user)
        assert (
            _client_for(user).delete(f"/api/v1/folders/{folder.id}/").status_code == 204
        )

    def test_delete_folder_with_documents_conflict(self):
        org = OrganizationFactory()
        user = _editor(org)
        folder = FolderFactory(organization=org, owner=user)
        DocumentFactory(organization=org, folder=folder, created_by=user)
        assert (
            _client_for(user).delete(f"/api/v1/folders/{folder.id}/").status_code == 409
        )

    def test_viewer_cannot_delete(self):
        org = OrganizationFactory()
        user = _viewer(org)
        folder = FolderFactory(organization=org, owner=user)
        assert (
            _client_for(user).delete(f"/api/v1/folders/{folder.id}/").status_code == 403
        )


@pytest.mark.django_db
class TestFolderChildren:
    def test_list_children(self):
        org = OrganizationFactory()
        user = _viewer(org)
        parent = FolderFactory(organization=org, owner=user)
        FolderFactory(organization=org, owner=user, parent=parent)
        response = _client_for(user).get(f"/api/v1/folders/{parent.id}/children/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Document API
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDocumentListCreate:
    def test_list_documents(self):
        org = OrganizationFactory()
        user = _viewer(org)
        DocumentFactory(organization=org, created_by=user)
        response = _client_for(user).get("/api/v1/documents/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1

    def test_list_documents_pagination_meta(self):
        org = OrganizationFactory()
        user = _viewer(org)
        meta = _client_for(user).get("/api/v1/documents/").json()["meta"]
        assert "count" in meta

    def test_list_documents_tenant_isolation(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user1 = _viewer(org1)
        user2 = _viewer(org2)
        DocumentFactory(organization=org1, created_by=user1)
        DocumentFactory(organization=org2, created_by=user2)
        assert len(_client_for(user1).get("/api/v1/documents/").json()["data"]) == 1

    def test_upload_document_editor(self, monkeypatch):
        org = OrganizationFactory()
        user = _editor(org)
        _storage_mock(monkeypatch)
        client = _client_for(user)
        f = io.BytesIO(PDF_HEADER + b"data")
        f.name = "test.pdf"
        response = client.post(
            "/api/v1/documents/",
            {"file": f, "name": "test.pdf"},
            format="multipart",
        )
        assert response.status_code == 201
        assert response.json()["data"]["name"] == "test.pdf"

    def test_upload_document_viewer_forbidden(self):
        org = OrganizationFactory()
        user = _viewer(org)
        client = _client_for(user)
        f = io.BytesIO(PDF_HEADER + b"data")
        f.name = "test.pdf"
        response = client.post(
            "/api/v1/documents/",
            {"file": f, "name": "test.pdf"},
            format="multipart",
        )
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self):
        assert APIClient().get("/api/v1/documents/").status_code == 401


@pytest.mark.django_db
class TestDocumentDetail:
    def test_get_document(self):
        org = OrganizationFactory()
        user = _viewer(org)
        doc = DocumentFactory(organization=org, created_by=user)
        response = _client_for(user).get(f"/api/v1/documents/{doc.id}/")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == str(doc.id)

    def test_get_document_wrong_org_not_found(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = _viewer(org1)
        doc = DocumentFactory(organization=org2)
        assert _client_for(user).get(f"/api/v1/documents/{doc.id}/").status_code == 404

    def test_patch_document_metadata(self):
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user)
        response = _client_for(user).patch(
            f"/api/v1/documents/{doc.id}/", {"name": "updated.pdf"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "updated.pdf"

    def test_patch_status_draft_to_under_review(self):
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        response = _client_for(user).patch(
            f"/api/v1/documents/{doc.id}/", {"status": "under_review"}, format="json"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "under_review"

    def test_patch_status_to_approved_rejected_by_serializer(self):
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        response = _client_for(user).patch(
            f"/api/v1/documents/{doc.id}/", {"status": "approved"}, format="json"
        )
        assert response.status_code == 400

    def test_delete_document(self):
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user)
        assert (
            _client_for(user).delete(f"/api/v1/documents/{doc.id}/").status_code == 204
        )

    def test_viewer_cannot_delete(self):
        org = OrganizationFactory()
        user = _viewer(org)
        doc = DocumentFactory(organization=org, created_by=user)
        assert (
            _client_for(user).delete(f"/api/v1/documents/{doc.id}/").status_code == 403
        )

    def test_unauthenticated_returns_401(self):
        org = OrganizationFactory()
        doc = DocumentFactory(organization=org)
        assert APIClient().get(f"/api/v1/documents/{doc.id}/").status_code == 401


@pytest.mark.django_db
class TestDocumentVersions:
    def test_list_versions(self):
        org = OrganizationFactory()
        user = _viewer(org)
        doc = DocumentFactory(organization=org, created_by=user)
        DocumentVersionFactory(document=doc, version_number=1, created_by=user)
        DocumentVersionFactory(document=doc, version_number=2, created_by=user)
        response = _client_for(user).get(f"/api/v1/documents/{doc.id}/versions/")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 2
        assert response.json()["data"][0]["version_number"] == 2


@pytest.mark.django_db
class TestReprocessOcr:
    def test_editor_can_reprocess_and_dispatches_task(
        self, django_capture_on_commit_callbacks
    ):
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user)
        with patch(
            "apps.documents.services.document_service.process_ocr.delay"
        ) as mock_delay:
            with django_capture_on_commit_callbacks(execute=True):
                response = _client_for(user).post(
                    f"/api/v1/documents/{doc.id}/reprocess-ocr/"
                )
        assert response.status_code == 202
        mock_delay.assert_called_once_with(str(doc.id))
        assert response.json()["data"]["ocr_status"] == "pending"

    def test_viewer_cannot_reprocess(self):
        org = OrganizationFactory()
        doc = DocumentFactory(organization=org)
        response = _client_for(_viewer(org)).post(
            f"/api/v1/documents/{doc.id}/reprocess-ocr/"
        )
        assert response.status_code == 403

    def test_reprocess_other_org_returns_404(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        doc_a = DocumentFactory(organization=org_a)
        response = _client_for(_editor(org_b)).post(
            f"/api/v1/documents/{doc_a.id}/reprocess-ocr/"
        )
        assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
class TestDocumentAnalyze:
    def test_editor_returns_202_with_envelope(
        self, settings, django_capture_on_commit_callbacks
    ):
        """Editor role gets 202 with {data: {...}} envelope; task is dispatched."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user, ocr_content="text")
        with patch(
            "apps.documents.tasks.document_tasks.analyze_document.delay"
        ) as mock_delay:
            with django_capture_on_commit_callbacks(execute=True):
                response = _client_for(user).post(
                    f"/api/v1/documents/{doc.id}/analyze/"
                )
        assert response.status_code == 202
        body = response.json()
        assert "data" in body
        assert body["data"]["id"] == str(doc.id)
        mock_delay.assert_called_once_with(str(doc.id))

    def test_viewer_returns_403(self, settings):
        """Viewer role is rejected."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        org = OrganizationFactory()
        doc = DocumentFactory(organization=org, ocr_content="text")
        response = _client_for(_viewer(org)).post(
            f"/api/v1/documents/{doc.id}/analyze/"
        )
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request is rejected."""
        org = OrganizationFactory()
        doc = DocumentFactory(organization=org)
        assert (
            APIClient().post(f"/api/v1/documents/{doc.id}/analyze/").status_code == 401
        )

    def test_missing_key_returns_503(self, settings):
        """When ANTHROPIC_API_KEY is empty the endpoint returns 503."""
        settings.ANTHROPIC_API_KEY = ""
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user, ocr_content="text")
        response = _client_for(user).post(f"/api/v1/documents/{doc.id}/analyze/")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "AI_SERVICE_UNAVAILABLE"

    def test_no_ocr_content_returns_409(self, settings):
        """Document with empty ocr_content returns 409 AI_NO_CONTENT."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        org = OrganizationFactory()
        user = _editor(org)
        doc = DocumentFactory(organization=org, created_by=user, ocr_content="")
        response = _client_for(user).post(f"/api/v1/documents/{doc.id}/analyze/")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "AI_NO_CONTENT"

    def test_tenant_isolation_returns_404(self, settings):
        """Document belonging to another org returns 404."""
        settings.ANTHROPIC_API_KEY = "sk-test-key"
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        doc_a = DocumentFactory(organization=org_a, ocr_content="text")
        response = _client_for(_editor(org_b)).post(
            f"/api/v1/documents/{doc_a.id}/analyze/"
        )
        assert response.status_code == 404
