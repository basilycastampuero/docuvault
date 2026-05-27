import pytest
from rest_framework.test import APIRequestFactory

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.permissions.permissions import (
    HasRole,
    IsOrgAdmin,
    IsOrganizationMember,
    IsSuperAdmin,
)


def make_request(user, organization=None):
    """Build a fake authenticated request with the given user and organization."""
    factory = APIRequestFactory()
    request = factory.get("/")
    request.user = user
    request.organization = organization
    return request


@pytest.mark.django_db
class TestIsOrganizationMember:
    def test_member_of_correct_org_passes(self, organization, user):
        request = make_request(user, organization=organization)
        assert IsOrganizationMember().has_permission(request, view=None) is True

    def test_member_of_different_org_is_denied(self, user):
        other_org = OrganizationFactory()
        request = make_request(user, organization=other_org)
        assert IsOrganizationMember().has_permission(request, view=None) is False

    def test_no_organization_on_request_is_denied(self, user):
        request = make_request(user, organization=None)
        assert IsOrganizationMember().has_permission(request, view=None) is False

    def test_unauthenticated_user_is_denied(self, organization):
        from django.contrib.auth.models import AnonymousUser

        request = make_request(AnonymousUser(), organization=organization)
        assert IsOrganizationMember().has_permission(request, view=None) is False


@pytest.mark.django_db
class TestHasRole:
    def test_user_with_correct_role_passes(self, organization):
        editor = UserFactory(organization=organization, role=UserRole.EDITOR)
        request = make_request(editor)
        assert HasRole(UserRole.EDITOR)().has_permission(request, view=None) is True

    def test_user_with_one_of_multiple_roles_passes(self, organization):
        supervisor = UserFactory(organization=organization, role=UserRole.SUPERVISOR)
        request = make_request(supervisor)
        perm = HasRole(UserRole.EDITOR, UserRole.SUPERVISOR)()
        assert perm.has_permission(request, view=None) is True

    def test_user_with_wrong_role_is_denied(self, organization):
        viewer = UserFactory(organization=organization, role=UserRole.VIEWER)
        request = make_request(viewer)
        assert HasRole(UserRole.EDITOR)().has_permission(request, view=None) is False

    def test_unauthenticated_user_is_denied(self):
        from django.contrib.auth.models import AnonymousUser

        request = make_request(AnonymousUser())
        assert HasRole(UserRole.VIEWER)().has_permission(request, view=None) is False


@pytest.mark.django_db
class TestIsSuperAdmin:
    def test_super_admin_passes(self):
        admin = UserFactory(organization=None, role=UserRole.SUPER_ADMIN)
        request = make_request(admin)
        assert IsSuperAdmin().has_permission(request, view=None) is True

    def test_org_admin_is_denied(self, organization):
        org_admin = UserFactory(organization=organization, role=UserRole.ORG_ADMIN)
        request = make_request(org_admin)
        assert IsSuperAdmin().has_permission(request, view=None) is False

    def test_viewer_is_denied(self, organization):
        viewer = UserFactory(organization=organization, role=UserRole.VIEWER)
        request = make_request(viewer)
        assert IsSuperAdmin().has_permission(request, view=None) is False


@pytest.mark.django_db
class TestIsOrgAdmin:
    def test_super_admin_passes(self):
        admin = UserFactory(organization=None, role=UserRole.SUPER_ADMIN)
        request = make_request(admin)
        assert IsOrgAdmin().has_permission(request, view=None) is True

    def test_org_admin_passes(self, organization):
        org_admin = UserFactory(organization=organization, role=UserRole.ORG_ADMIN)
        request = make_request(org_admin)
        assert IsOrgAdmin().has_permission(request, view=None) is True

    def test_editor_is_denied(self, organization):
        editor = UserFactory(organization=organization, role=UserRole.EDITOR)
        request = make_request(editor)
        assert IsOrgAdmin().has_permission(request, view=None) is False

    def test_viewer_is_denied(self, organization):
        viewer = UserFactory(organization=organization, role=UserRole.VIEWER)
        request = make_request(viewer)
        assert IsOrgAdmin().has_permission(request, view=None) is False
