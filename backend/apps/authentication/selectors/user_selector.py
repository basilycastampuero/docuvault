from django.db.models import QuerySet

from apps.authentication.models import User
from apps.core.exceptions import NotFound
from apps.organizations.models import Organization


def get_users_by_organization(organization: Organization) -> QuerySet:
    """Return all active users belonging to the given organization."""
    return User.objects.filter(organization=organization).select_related("organization")


def get_user_by_id(organization: Organization, user_id: str) -> User:
    """Return a user by id, scoped to the given organization."""
    try:
        return User.objects.select_related("organization").get(
            id=user_id, organization=organization
        )
    except User.DoesNotExist:
        raise NotFound(
            message=f"User {user_id} not found in this organization",
            code="USER_NOT_FOUND",
        )
