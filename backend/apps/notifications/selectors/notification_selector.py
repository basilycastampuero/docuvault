from typing import TYPE_CHECKING

from django.db.models import QuerySet

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization


def get_recipients_for_role(
    organization: "Organization",
    role: str,
) -> "QuerySet[User]":
    """Return active users in the org with the given role. Tenant-safe."""
    from apps.authentication.models import User

    return User.objects.filter(
        organization=organization,
        role=role,
        is_active=True,
    )
