import logging

from apps.authentication.models import User, UserRole
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError
from apps.organizations.models import Organization

logger = logging.getLogger(__name__)


def create_user(
    organization: Organization,
    email: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    password: str | None = None,
) -> User:
    """Create a new user in the given organization."""
    if User.objects.filter(email=email).exists():
        raise ConflictError(
            message=f"A user with email '{email}' already exists",
            code="EMAIL_TAKEN",
        )

    if role == UserRole.SUPER_ADMIN:
        raise ValidationError(
            message="Cannot create a SUPER_ADMIN user through this endpoint",
            code="INVALID_ROLE",
        )

    user = User.objects.create_user(
        email=email,
        password=password,
        organization=organization,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    logger.info("User %s created in org %s", user.email, organization.slug)
    return user


def update_user(
    organization: Organization,
    user: User,
    requesting_user: User,
    first_name: str | None = None,
    last_name: str | None = None,
    role: str | None = None,
) -> User:
    """Update an existing user. A user cannot change their own role."""
    if role is not None and user.id == requesting_user.id:
        raise PermissionDenied(
            message="You cannot change your own role",
            code="CANNOT_CHANGE_OWN_ROLE",
        )

    if role is not None and role == UserRole.SUPER_ADMIN:
        raise ValidationError(
            message="Cannot assign the SUPER_ADMIN role through this endpoint",
            code="INVALID_ROLE",
        )

    update_fields = ["updated_at"]

    if first_name is not None:
        user.first_name = first_name
        update_fields.append("first_name")

    if last_name is not None:
        user.last_name = last_name
        update_fields.append("last_name")

    if role is not None:
        user.role = role
        update_fields.append("role")

    user.save(update_fields=update_fields)
    logger.info("User %s updated in org %s", user.email, organization.slug)
    return user


def deactivate_user(
    organization: Organization,
    user: User,
    requesting_user: User,
) -> None:
    """Deactivate a user — sets is_active=False (not a soft delete)."""
    if user.id == requesting_user.id:
        raise PermissionDenied(
            message="You cannot deactivate your own account",
            code="CANNOT_DEACTIVATE_SELF",
        )

    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    logger.info("User %s deactivated in org %s", user.email, organization.slug)
