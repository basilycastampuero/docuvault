"""HTTP transport helpers for the auth cookie scheme (Phase 6.1).

Pure request/response utilities — no business logic. They live next to the
views (not in `services/`) because they only deal with how tokens travel over
HTTP (cookies, headers), not with authentication/authorization rules.
"""

import secrets

from django.conf import settings
from django.http import HttpRequest
from rest_framework.response import Response

CSRF_HEADER_NAME = "X-CSRF-Token"


def _refresh_cookie_max_age() -> int:
    """Return the refresh cookie lifetime in seconds, mirrored from SIMPLE_JWT."""
    return int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Attach the refresh token as an HttpOnly cookie scoped to the auth path."""
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=_refresh_cookie_max_age(),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=settings.AUTH_REFRESH_COOKIE_HTTPONLY,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire the refresh cookie, e.g. on logout."""
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


def issue_csrf_cookie(response: Response) -> str:
    """Generate a random CSRF token, set it as a non-HttpOnly cookie, and return it.

    Non-HttpOnly by design: the frontend JS must read it back to echo it in the
    `X-CSRF-Token` header (double-submit pattern).
    """
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.AUTH_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=_refresh_cookie_max_age(),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=False,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )
    return csrf_token


def get_refresh_from_cookie(request: HttpRequest) -> str | None:
    """Read the refresh token from its HttpOnly cookie, if present."""
    return request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME) or None


def validate_csrf(request: HttpRequest) -> bool:
    """Validate the double-submit CSRF token: cookie value must match the header."""
    cookie_value = request.COOKIES.get(settings.AUTH_CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    return bool(cookie_value) and secrets.compare_digest(
        cookie_value, header_value or ""
    )
