import pytest
from rest_framework import status

from apps.authentication.tests.factories import UserFactory


@pytest.mark.django_db
class TestLoginEndpoint:
    url = "/api/v1/auth/login/"

    def test_valid_credentials_return_200(self, api_client, user):
        response = api_client.post(
            self.url, {"email": user.email, "password": "testpass123"}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_response_contains_access_and_refresh(self, api_client, user):
        response = api_client.post(
            self.url, {"email": user.email, "password": "testpass123"}
        )
        assert "access" in response.data["data"]
        assert "refresh" in response.data["data"]

    def test_response_contains_user_data(self, api_client, user):
        response = api_client.post(
            self.url, {"email": user.email, "password": "testpass123"}
        )
        assert response.data["data"]["user"]["email"] == user.email

    def test_wrong_password_returns_400(self, api_client, user):
        response = api_client.post(self.url, {"email": user.email, "password": "wrong"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "INVALID_CREDENTIALS"

    def test_missing_email_returns_400(self, api_client):
        response = api_client.post(self.url, {"password": "pass"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_password_returns_400(self, api_client):
        response = api_client.post(self.url, {"email": "a@example.com"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_inactive_user_returns_400(self, api_client, organization):
        inactive = UserFactory(organization=organization, is_active=False)
        response = api_client.post(
            self.url, {"email": inactive.email, "password": "testpass123"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "ACCOUNT_DISABLED"


@pytest.mark.django_db
class TestLogoutEndpoint:
    url = "/api/v1/auth/logout/"
    login_url = "/api/v1/auth/login/"

    def _login(self, api_client, user):
        response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        return response.data["data"]

    def test_valid_logout_returns_204(self, api_client, user):
        tokens = self._login(api_client, user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = api_client.post(self.url, {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_unauthenticated_logout_returns_401(self, api_client, user):
        tokens = self._login(api_client, user)
        response = api_client.post(self.url, {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_returns_400(self, api_client, user):
        tokens = self._login(api_client, user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = api_client.post(self.url, {"refresh": "not.a.token"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.django_db
class TestRefreshEndpoint:
    url = "/api/v1/auth/refresh/"
    login_url = "/api/v1/auth/login/"

    def _login(self, api_client, user):
        response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        return response.data["data"]

    def test_valid_refresh_returns_200(self, api_client, user):
        tokens = self._login(api_client, user)
        response = api_client.post(self.url, {"refresh": tokens["refresh"]})
        assert response.status_code == status.HTTP_200_OK

    def test_response_contains_new_access_token(self, api_client, user):
        tokens = self._login(api_client, user)
        response = api_client.post(self.url, {"refresh": tokens["refresh"]})
        assert "access" in response.data["data"]

    def test_invalid_token_returns_400(self, api_client):
        response = api_client.post(self.url, {"refresh": "not.a.token"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.django_db
class TestMeEndpoint:
    url = "/api/v1/auth/me/"
    login_url = "/api/v1/auth/login/"

    def test_authenticated_user_gets_own_data(self, api_client, user):
        response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        token = response.data["data"]["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["email"] == user.email

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_contains_role(self, api_client, user):
        response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        token = response.data["data"]["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get(self.url)
        assert "role" in response.data["data"]
        assert response.data["data"]["role"] == user.role
