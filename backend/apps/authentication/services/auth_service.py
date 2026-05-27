import logging

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import User
from apps.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _build_token_pair(user: User) -> dict:
    """Generate JWT pair with custom claims (organization_id, role, email)."""
    refresh = RefreshToken.for_user(user)

    org_id = str(user.organization_id) if user.organization_id else None
    for token in (refresh, refresh.access_token):
        token["organization_id"] = org_id
        token["role"] = user.role
        token["email"] = user.email

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def login(email: str, password: str) -> dict:
    """Authenticate user credentials and return a JWT pair plus user instance."""
    # We do manual verification so we can distinguish INVALID_CREDENTIALS from
    # ACCOUNT_DISABLED. Django's authenticate() returns None for both cases.
    try:
        user = User.all_objects.get(email=email)
    except User.DoesNotExist:
        raise ValidationError(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS",
        )

    if not user.check_password(password) or user.is_deleted:
        raise ValidationError(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS",
        )

    if not user.is_active:
        raise ValidationError(
            message="This account has been deactivated",
            code="ACCOUNT_DISABLED",
        )

    logger.info("User %s logged in", user.email)
    tokens = _build_token_pair(user)
    return {**tokens, "user": user}


def logout(refresh_token: str) -> None:
    """Blacklist the given refresh token, invalidating the session."""
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError as exc:
        raise ValidationError(
            message="Invalid or expired token",
            code="INVALID_TOKEN",
        ) from exc


def refresh_token_pair(refresh_token: str) -> dict:
    """Rotate a refresh token and return a new token pair with updated claims."""
    try:
        old_refresh = RefreshToken(refresh_token)
        user_id = old_refresh["user_id"]
        user = User.objects.get(id=user_id)
    except (TokenError, User.DoesNotExist) as exc:
        raise ValidationError(
            message="Invalid or expired token",
            code="INVALID_TOKEN",
        ) from exc

    old_refresh.blacklist()
    return _build_token_pair(user)
