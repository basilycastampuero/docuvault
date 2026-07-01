import pytest

from apps.authentication.services import auth_service
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import ValidationError


@pytest.mark.django_db
class TestLogin:
    def test_returns_access_token(self, user):
        result = auth_service.login(email=user.email, password="testpass123")
        assert "access" in result
        assert result["access"]

    def test_returns_refresh_token(self, user):
        result = auth_service.login(email=user.email, password="testpass123")
        assert "refresh" in result
        assert result["refresh"]

    def test_returns_user_instance(self, user):
        result = auth_service.login(email=user.email, password="testpass123")
        assert result["user"].id == user.id

    def test_wrong_password_raises_validation_error(self, user):
        with pytest.raises(ValidationError) as exc_info:
            auth_service.login(email=user.email, password="wrongpassword")
        assert exc_info.value.code == "INVALID_CREDENTIALS"

    def test_unknown_email_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            auth_service.login(email="ghost@example.com", password="pass")
        assert exc_info.value.code == "INVALID_CREDENTIALS"

    def test_inactive_user_raises_validation_error(self, organization):
        inactive = UserFactory(organization=organization, is_active=False)
        with pytest.raises(ValidationError) as exc_info:
            auth_service.login(email=inactive.email, password="testpass123")
        assert exc_info.value.code == "ACCOUNT_DISABLED"

    def test_token_contains_organization_id(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        result = auth_service.login(email=user.email, password="testpass123")
        payload = AccessToken(result["access"])
        assert str(payload["organization_id"]) == str(user.organization_id)

    def test_token_contains_role(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        result = auth_service.login(email=user.email, password="testpass123")
        payload = AccessToken(result["access"])
        assert payload["role"] == user.role

    def test_token_contains_email(self, user):
        from rest_framework_simplejwt.tokens import AccessToken

        result = auth_service.login(email=user.email, password="testpass123")
        payload = AccessToken(result["access"])
        assert payload["email"] == user.email


@pytest.mark.django_db
class TestLogout:
    def test_valid_refresh_token_is_blacklisted(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken

        tokens = auth_service.login(email=user.email, password="testpass123")
        auth_service.logout(tokens["refresh"])

        # Trying to use the blacklisted token should raise TokenError
        from rest_framework_simplejwt.exceptions import TokenError

        with pytest.raises(TokenError):
            RefreshToken(tokens["refresh"])

    def test_invalid_token_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            auth_service.logout("not.a.valid.token")
        assert exc_info.value.code == "INVALID_TOKEN"


@pytest.mark.django_db
class TestRefreshTokenPair:
    def test_returns_new_access_token(self, user):
        tokens = auth_service.login(email=user.email, password="testpass123")
        new_tokens = auth_service.refresh_token_pair(tokens["refresh"])
        assert "access" in new_tokens
        assert new_tokens["access"] != tokens["access"]

    def test_old_refresh_token_is_blacklisted_after_rotation(self, user):
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import RefreshToken

        tokens = auth_service.login(email=user.email, password="testpass123")
        auth_service.refresh_token_pair(tokens["refresh"])

        with pytest.raises(TokenError):
            RefreshToken(tokens["refresh"])

    def test_invalid_token_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            auth_service.refresh_token_pair("not.a.valid.token")
        assert exc_info.value.code == "INVALID_TOKEN"
