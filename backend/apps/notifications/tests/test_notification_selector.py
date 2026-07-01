import pytest

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.notifications.selectors import notification_selector
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestGetRecipientsForRole:
    def test_returns_matching_users(self):
        """Should return active users in the org who hold the given role."""
        org = OrganizationFactory()
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        # Other roles in the same org — must not appear
        UserFactory(organization=org, role=UserRole.VIEWER)
        UserFactory(organization=org, role=UserRole.SUPERVISOR)

        qs = notification_selector.get_recipients_for_role(org, UserRole.EDITOR)

        assert list(qs) == [editor]

    def test_tenant_isolation(self):
        """Should not return users from a different organization."""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        # Editor in org B only
        UserFactory(organization=org_b, role=UserRole.EDITOR)

        qs = notification_selector.get_recipients_for_role(org_a, UserRole.EDITOR)

        assert qs.count() == 0

    def test_excludes_inactive_users(self):
        """Should exclude inactive users even when they hold the correct role."""
        org = OrganizationFactory()
        UserFactory(organization=org, role=UserRole.SUPERVISOR, is_active=False)

        qs = notification_selector.get_recipients_for_role(org, UserRole.SUPERVISOR)

        assert qs.count() == 0

    def test_returns_empty_when_no_match(self):
        """Should return an empty queryset when no user holds the requested role."""
        org = OrganizationFactory()
        UserFactory(organization=org, role=UserRole.VIEWER)

        qs = notification_selector.get_recipients_for_role(org, UserRole.ORG_ADMIN)

        assert qs.count() == 0

    def test_returns_multiple_matching_users(self):
        """Should return all active users with the role, not just the first one."""
        org = OrganizationFactory()
        editors = [
            UserFactory(organization=org, role=UserRole.EDITOR) for _ in range(3)
        ]

        qs = notification_selector.get_recipients_for_role(org, UserRole.EDITOR)

        assert set(qs) == set(editors)
