import uuid

import pytest
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization
from apps.organizations.tests.factories import OrganizationFactory

User = get_user_model()


@pytest.mark.django_db
class TestOrganizationListAPI:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/organizations/")
        assert response.status_code == 401
        assert "error" in response.data

    def test_authenticated_returns_200(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.get("/api/v1/organizations/")
        assert response.status_code == 200
        assert "data" in response.data
        assert "meta" in response.data

    def test_returns_only_active_organizations(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        active = OrganizationFactory()
        OrganizationFactory(is_active=False)
        response = api_client.get("/api/v1/organizations/")
        ids = [item["id"] for item in response.data["data"]]
        assert str(active.id) in ids

    def test_meta_count_matches_results(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.get("/api/v1/organizations/")
        assert response.data["meta"]["count"] == len(response.data["data"])


@pytest.mark.django_db
class TestOrganizationCreateAPI:
    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post("/api/v1/organizations/", {"name": "New Org"})
        assert response.status_code == 401

    def test_creates_organization(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.post("/api/v1/organizations/", {"name": "New Org"})
        assert response.status_code == 201
        assert response.data["data"]["name"] == "New Org"
        assert response.data["data"]["slug"] == "new-org"

    def test_create_with_custom_slug(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.post(
            "/api/v1/organizations/", {"name": "New Org", "slug": "my-custom-slug"}
        )
        assert response.status_code == 201
        assert response.data["data"]["slug"] == "my-custom-slug"

    def test_duplicate_slug_returns_409(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.post(
            "/api/v1/organizations/",
            {"name": "Another Org", "slug": organization.slug},
        )
        assert response.status_code == 409
        assert response.data["error"]["code"] == "SLUG_TAKEN"

    def test_missing_name_returns_400(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.post("/api/v1/organizations/", {})
        assert response.status_code == 400
        assert "error" in response.data


@pytest.mark.django_db
class TestOrganizationRetrieveAPI:
    def test_returns_organization(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.get(f"/api/v1/organizations/{organization.id}/")
        assert response.status_code == 200
        assert response.data["data"]["id"] == str(organization.id)
        assert response.data["data"]["name"] == organization.name

    def test_unknown_id_returns_404(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.get(f"/api/v1/organizations/{uuid.uuid4()}/")
        assert response.status_code == 404
        assert response.data["error"]["code"] == "NOT_FOUND"

    def test_unauthenticated_returns_401(self, api_client, organization):
        response = api_client.get(f"/api/v1/organizations/{organization.id}/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestOrganizationUpdateAPI:
    def test_updates_name(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.patch(
            f"/api/v1/organizations/{organization.id}/", {"name": "Updated Name"}
        )
        assert response.status_code == 200
        assert response.data["data"]["name"] == "Updated Name"

    def test_slug_not_changed_by_name_update(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        original_slug = organization.slug
        api_client.patch(
            f"/api/v1/organizations/{organization.id}/", {"name": "Completely New Name"}
        )
        organization.refresh_from_db()
        assert organization.slug == original_slug

    def test_blank_name_returns_400(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.patch(
            f"/api/v1/organizations/{organization.id}/", {"name": "   "}
        )
        assert response.status_code == 400

    def test_unknown_id_returns_404(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.patch(
            f"/api/v1/organizations/{uuid.uuid4()}/", {"name": "X"}
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestOrganizationDeactivateAPI:
    def test_deactivates_organization(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        response = api_client.delete(f"/api/v1/organizations/{organization.id}/")
        assert response.status_code == 204
        organization.refresh_from_db()
        assert organization.is_active is False

    def test_does_not_hard_delete(self, api_client, auth_user, organization):
        api_client.force_authenticate(user=auth_user)
        org_id = organization.id
        api_client.delete(f"/api/v1/organizations/{organization.id}/")
        assert Organization.objects.filter(id=org_id).exists()

    def test_unknown_id_returns_404(self, api_client, auth_user):
        api_client.force_authenticate(user=auth_user)
        response = api_client.delete(f"/api/v1/organizations/{uuid.uuid4()}/")
        assert response.status_code == 404
