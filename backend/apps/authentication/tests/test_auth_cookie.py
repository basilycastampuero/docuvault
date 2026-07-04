"""Tests for the JWT refresh-cookie scheme (Phase 6.1).

Covers the HttpOnly `sv_refresh` cookie + non-HttpOnly `sv_csrf` double-submit
cookie, gated by `AUTH_REFRESH_COOKIE_ENABLED` (default True). Uses the DRF
`APIClient`, which behaves like a real browser and persists `Set-Cookie`
values across requests made with the same client instance — so cookies must
be explicitly cleared/overwritten to simulate a "fresh" client.
"""

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken


@pytest.mark.django_db
class TestLoginCookieBehavior:
    login_url = "/api/v1/auth/login/"

    def _login(self, api_client, user):
        return api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )

    def test_sets_httponly_refresh_cookie(self, api_client, user):
        """Should set `sv_refresh` as an HttpOnly cookie on successful login."""
        response = self._login(api_client, user)
        refresh_cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        assert refresh_cookie.value
        assert refresh_cookie["httponly"] is True

    def test_refresh_cookie_secure_flag_matches_settings(self, api_client, user):
        """Should mirror `AUTH_REFRESH_COOKIE_SECURE` exactly (False in test settings)."""
        response = self._login(api_client, user)
        refresh_cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        assert bool(refresh_cookie["secure"]) == settings.AUTH_REFRESH_COOKIE_SECURE

    def test_refresh_cookie_samesite_is_strict(self, api_client, user):
        """Should set SameSite=Strict on the refresh cookie."""
        response = self._login(api_client, user)
        refresh_cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        assert refresh_cookie["samesite"] == "Strict"

    def test_sets_non_httponly_csrf_cookie(self, api_client, user):
        """Should set `sv_csrf` as a non-HttpOnly cookie so JS can echo it back."""
        response = self._login(api_client, user)
        csrf_cookie = response.cookies[settings.AUTH_CSRF_COOKIE_NAME]
        assert csrf_cookie.value
        assert not csrf_cookie["httponly"]

    def test_response_body_excludes_refresh_token(self, api_client, user):
        """Should never expose the refresh token in the JSON body when cookie mode is on."""
        response = self._login(api_client, user)
        assert "refresh" not in response.data["data"]
        assert "access" in response.data["data"]


@pytest.mark.django_db
class TestRefreshCookieBehavior:
    login_url = "/api/v1/auth/login/"
    refresh_url = "/api/v1/auth/refresh/"

    def _login(self, api_client, user):
        return api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )

    def test_valid_cookie_and_csrf_rotates_refresh_token(self, api_client, user):
        """Should return 200, a new access token, and rotate the refresh cookie value."""
        login_response = self._login(api_client, user)
        old_refresh_value = login_response.cookies[
            settings.AUTH_REFRESH_COOKIE_NAME
        ].value
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        response = api_client.post(self.refresh_url, HTTP_X_CSRF_TOKEN=csrf)

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["data"]
        new_refresh_value = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        assert new_refresh_value != old_refresh_value

    def test_missing_csrf_header_returns_403(self, api_client, user):
        """Should reject the rotation with 403 CSRF_INVALID when no header is sent."""
        self._login(api_client, user)
        response = api_client.post(self.refresh_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "CSRF_INVALID"

    def test_mismatched_csrf_header_returns_403(self, api_client, user):
        """Should reject the rotation with 403 CSRF_INVALID when the header doesn't match the cookie."""
        self._login(api_client, user)
        response = api_client.post(
            self.refresh_url, HTTP_X_CSRF_TOKEN="not-the-real-token"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "CSRF_INVALID"

    def test_no_cookie_and_no_body_refresh_returns_401(self, api_client):
        """Should return 401 INVALID_TOKEN when neither a cookie nor a body refresh is provided."""
        response = api_client.post(self.refresh_url, {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"]["code"] == "INVALID_TOKEN"

    def test_body_fallback_without_cookie_still_works(self, api_client, user):
        """Should still rotate via the body-only refresh during the transition window."""
        # Log in with the cookie flag off so no refresh cookie is ever set,
        # forcing the refresh view down its body-fallback branch.
        with override_settings(AUTH_REFRESH_COOKIE_ENABLED=False):
            body_login = api_client.post(
                self.login_url, {"email": user.email, "password": "testpass123"}
            )
        refresh_token = body_login.data["data"]["refresh"]

        response = api_client.post(self.refresh_url, {"refresh": refresh_token})
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data["data"]

    def test_blacklisted_refresh_is_rejected_on_reuse(self, api_client, user):
        """Should reject a refresh token that was already blacklisted by logout."""
        login_response = self._login(api_client, user)
        refresh_value = login_response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        logout_response = api_client.post(
            "/api/v1/auth/logout/", HTTP_X_CSRF_TOKEN=csrf
        )
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT

        # Manually re-attach the now-blacklisted refresh cookie to simulate reuse.
        api_client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = refresh_value
        api_client.cookies[settings.AUTH_CSRF_COOKIE_NAME] = csrf

        response = api_client.post(self.refresh_url, HTTP_X_CSRF_TOKEN=csrf)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.django_db
class TestLogoutCookieBehavior:
    login_url = "/api/v1/auth/login/"
    logout_url = "/api/v1/auth/logout/"
    refresh_url = "/api/v1/auth/refresh/"

    def _login(self, api_client, user):
        return api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )

    def test_valid_cookie_and_csrf_blacklists_refresh_token(self, api_client, user):
        """Should blacklist the refresh token so a subsequent refresh with it fails."""
        login_response = self._login(api_client, user)
        refresh_value = login_response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        logout_response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN=csrf)
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT

        api_client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = refresh_value
        api_client.cookies[settings.AUTH_CSRF_COOKIE_NAME] = csrf
        reuse_response = api_client.post(self.refresh_url, HTTP_X_CSRF_TOKEN=csrf)
        assert reuse_response.status_code == status.HTTP_400_BAD_REQUEST
        assert reuse_response.data["error"]["code"] == "INVALID_TOKEN"

    def test_valid_logout_clears_the_refresh_cookie(self, api_client, user):
        """Should expire the `sv_refresh` cookie in the logout response."""
        login_response = self._login(api_client, user)
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN=csrf)
        cleared_cookie = response.cookies[settings.AUTH_REFRESH_COOKIE_NAME]
        assert cleared_cookie.value == ""
        assert int(cleared_cookie["max-age"]) == 0

    def test_without_authorization_header_still_succeeds(self, api_client, user):
        """Should return 204 with no Authorization header — refresh cookie + CSRF
        is sufficient proof of identity, justifying the AllowAny permission."""
        login_response = self._login(api_client, user)
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        # No api_client.credentials(...) call at all: no Authorization header.
        response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN=csrf)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_double_logout_does_not_raise_and_returns_204(self, api_client, user):
        """Should not raise on a second logout with the already-blacklisted token."""
        login_response = self._login(api_client, user)
        refresh_value = login_response.cookies[settings.AUTH_REFRESH_COOKIE_NAME].value
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        first_response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN=csrf)
        assert first_response.status_code == status.HTTP_204_NO_CONTENT

        # Re-attach the blacklisted refresh cookie to force a second logout attempt.
        api_client.cookies[settings.AUTH_REFRESH_COOKIE_NAME] = refresh_value
        api_client.cookies[settings.AUTH_CSRF_COOKIE_NAME] = csrf
        second_response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN=csrf)
        assert second_response.status_code == status.HTTP_204_NO_CONTENT

    def test_invalid_csrf_returns_403_and_does_not_clear_cookie(self, api_client, user):
        """Should reject with 403 CSRF_INVALID and leave the refresh cookie untouched."""
        self._login(api_client, user)

        response = api_client.post(self.logout_url, HTTP_X_CSRF_TOKEN="wrong-token")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"]["code"] == "CSRF_INVALID"
        assert settings.AUTH_REFRESH_COOKIE_NAME not in response.cookies


@pytest.mark.django_db
class TestTenantIsolationViaCookieRefresh:
    """Verifies that rotating tokens by cookie never leaks or mixes claims
    between organizations — CLAUDE.md §4/§11 tenant isolation requirement."""

    login_url = "/api/v1/auth/login/"
    refresh_url = "/api/v1/auth/refresh/"
    me_url = "/api/v1/auth/me/"

    def _login(self, api_client, target_user):
        return api_client.post(
            self.login_url, {"email": target_user.email, "password": "testpass123"}
        )

    def test_refreshed_access_token_keeps_own_organization_claims(
        self, api_client, user, other_user
    ):
        """Should mint an access token carrying only the requesting user's own
        organization_id, never another org's, when rotated via cookie."""
        assert user.organization_id != other_user.organization_id

        login_response = self._login(api_client, user)
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        response = api_client.post(self.refresh_url, HTTP_X_CSRF_TOKEN=csrf)
        assert response.status_code == status.HTTP_200_OK

        new_access = AccessToken(response.data["data"]["access"])
        assert new_access["organization_id"] == str(user.organization_id)
        assert new_access["organization_id"] != str(other_user.organization_id)

    def test_refreshed_access_token_resolves_to_the_correct_user_via_me(
        self, api_client, user, other_user
    ):
        """Should authenticate as the original user (not another org's user) via /me/."""
        login_response = self._login(api_client, user)
        csrf = login_response.cookies[settings.AUTH_CSRF_COOKIE_NAME].value

        refresh_response = api_client.post(self.refresh_url, HTTP_X_CSRF_TOKEN=csrf)
        new_access = refresh_response.data["data"]["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        me_response = api_client.get(self.me_url)

        assert me_response.status_code == status.HTTP_200_OK
        assert me_response.data["data"]["email"] == user.email
        assert me_response.data["data"]["email"] != other_user.email
        assert me_response.data["data"]["organization_id"] == user.organization_id


@pytest.mark.django_db
class TestLegacyBodyModeWhenCookieDisabled:
    """Legacy behavior preserved when AUTH_REFRESH_COOKIE_ENABLED=False.

    Uses the pytest-django `settings` fixture (not `override_settings` as a
    class decorator, which only works on `SimpleTestCase` subclasses).
    """

    login_url = "/api/v1/auth/login/"
    refresh_url = "/api/v1/auth/refresh/"
    logout_url = "/api/v1/auth/logout/"

    def test_login_exposes_refresh_in_body_and_sets_no_cookies(
        self, api_client, user, settings
    ):
        """Should return refresh in the body and set no auth cookies when the flag is off."""
        settings.AUTH_REFRESH_COOKIE_ENABLED = False
        response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        assert "refresh" in response.data["data"]
        assert settings.AUTH_REFRESH_COOKIE_NAME not in response.cookies
        assert settings.AUTH_CSRF_COOKIE_NAME not in response.cookies

    def test_refresh_and_logout_work_via_body_only(self, api_client, user, settings):
        """Should rotate and then blacklist the refresh token entirely via the body."""
        settings.AUTH_REFRESH_COOKIE_ENABLED = False
        login_response = api_client.post(
            self.login_url, {"email": user.email, "password": "testpass123"}
        )
        refresh_token = login_response.data["data"]["refresh"]
        access_token = login_response.data["data"]["access"]

        refresh_response = api_client.post(self.refresh_url, {"refresh": refresh_token})
        assert refresh_response.status_code == status.HTTP_200_OK

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = api_client.post(
            self.logout_url,
            {"refresh": refresh_response.data["data"]["refresh"]},
        )
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT
