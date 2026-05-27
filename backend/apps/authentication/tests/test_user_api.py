import pytest
from rest_framework import status

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory


def login(api_client, user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": "testpass123"},
    )
    token = response.data["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
class TestListUsers:
    url = "/api/v1/users/"

    def test_org_admin_can_list_users(self, api_client, org_admin, user):
        login(api_client, org_admin)
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        user_ids = [u["id"] for u in response.data["data"]]
        assert str(user.id) in user_ids

    def test_viewer_can_list_users(self, api_client, user):
        login(api_client, user)
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_does_not_return_users_from_other_org(self, api_client, org_admin):
        other_org = OrganizationFactory()
        UserFactory(organization=other_org)
        login(api_client, org_admin)
        response = api_client.get(self.url)
        org_ids = {u["organization_id"] for u in response.data["data"]}
        assert all(str(oid) == str(org_admin.organization_id) for oid in org_ids)

    def test_response_contains_meta_count(self, api_client, org_admin):
        login(api_client, org_admin)
        response = api_client.get(self.url)
        assert "count" in response.data["meta"]


@pytest.mark.django_db
class TestCreateUser:
    url = "/api/v1/users/"

    def test_org_admin_can_create_user(self, api_client, org_admin, organization):
        login(api_client, org_admin)
        response = api_client.post(
            self.url,
            {"email": "newbie@example.com", "role": UserRole.VIEWER},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["email"] == "newbie@example.com"

    def test_viewer_cannot_create_user(self, api_client, user):
        login(api_client, user)
        response = api_client.post(
            self.url,
            {"email": "should@fail.com", "role": UserRole.VIEWER},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_duplicate_email_returns_409(self, api_client, org_admin, user):
        login(api_client, org_admin)
        response = api_client.post(
            self.url,
            {"email": user.email, "role": UserRole.VIEWER},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "EMAIL_TAKEN"

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            self.url,
            {"email": "x@example.com", "role": UserRole.VIEWER},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestGetUser:
    def test_org_admin_can_get_user(self, api_client, org_admin, user):
        login(api_client, org_admin)
        response = api_client.get(f"/api/v1/users/{user.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(user.id)

    def test_viewer_can_get_user(self, api_client, user, org_admin):
        login(api_client, user)
        response = api_client.get(f"/api/v1/users/{org_admin.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_cannot_get_user_from_other_org(self, api_client, org_admin):
        other_user = UserFactory(organization=OrganizationFactory())
        login(api_client, org_admin)
        response = api_client.get(f"/api/v1/users/{other_user.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUpdateUser:
    def test_org_admin_can_update_user(self, api_client, org_admin, user):
        login(api_client, org_admin)
        response = api_client.patch(
            f"/api/v1/users/{user.id}/",
            {"first_name": "Updated"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["first_name"] == "Updated"

    def test_viewer_cannot_update_user(self, api_client, user, org_admin):
        login(api_client, user)
        response = api_client.patch(
            f"/api/v1/users/{org_admin.id}/",
            {"first_name": "Hacked"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_change_own_role_returns_403(self, api_client, org_admin):
        login(api_client, org_admin)
        response = api_client.patch(
            f"/api/v1/users/{org_admin.id}/",
            {"role": UserRole.VIEWER},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "CANNOT_CHANGE_OWN_ROLE"


@pytest.mark.django_db
class TestDeactivateUser:
    def test_org_admin_can_deactivate_user(self, api_client, org_admin, user):
        login(api_client, org_admin)
        response = api_client.delete(f"/api/v1/users/{user.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_viewer_cannot_deactivate_user(self, api_client, user, org_admin):
        login(api_client, user)
        response = api_client.delete(f"/api/v1/users/{org_admin.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_deactivate_self_returns_403(self, api_client, org_admin):
        login(api_client, org_admin)
        response = api_client.delete(f"/api/v1/users/{org_admin.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "CANNOT_DEACTIVATE_SELF"
