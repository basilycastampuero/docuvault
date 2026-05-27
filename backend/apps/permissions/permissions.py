from rest_framework.permissions import BasePermission

from apps.authentication.models import UserRole


class IsOrganizationMember(BasePermission):
    """
    Allows access only to users who belong to request.organization.
    Requires OrganizationTenantMiddleware to have run (sets request.organization).
    """

    message = "You are not a member of this organization."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.organization is None:
            return False
        return request.user.organization_id == request.organization.id


def HasRole(*roles: str):
    """
    Permission class factory. Returns a class that allows access only to users
    whose role is one of the given roles.

    Usage:
        permission_classes = [IsAuthenticated, HasRole(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)]
    """

    class _HasRole(BasePermission):
        required_roles = roles
        message = f"Required role: {', '.join(roles)}."

        def has_permission(self, request, view) -> bool:
            if not request.user or not request.user.is_authenticated:
                return False
            return request.user.role in self.required_roles

    _HasRole.__name__ = f"HasRole({', '.join(roles)})"
    return _HasRole


# Convenience classes for the most common role checks

IsSuperAdmin = HasRole(UserRole.SUPER_ADMIN)

# OrgAdmin includes SuperAdmin because SuperAdmin can do everything OrgAdmin can
IsOrgAdmin = HasRole(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)

IsSuperAdminOrOrgAdmin = IsOrgAdmin  # alias for readability
