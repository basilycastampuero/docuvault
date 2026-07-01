import pytest

from apps.authentication.selectors import user_selector
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import NotFound
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestGetUsersByOrganization:
    def test_returns_users_of_organization(self, organization, user):
        result = user_selector.get_users_by_organization(organization)
        assert user in result

    def test_does_not_return_users_from_other_org(self, organization, user):
        other_org = OrganizationFactory()
        other_user = UserFactory(organization=other_org)
        result = user_selector.get_users_by_organization(organization)
        assert other_user not in result

    def test_does_not_return_soft_deleted_users(self, organization):
        deleted = UserFactory(organization=organization)
        deleted.soft_delete()
        result = user_selector.get_users_by_organization(organization)
        assert deleted not in result


@pytest.mark.django_db
class TestGetUserById:
    def test_returns_correct_user(self, organization, user):
        result = user_selector.get_user_by_id(organization, user.id)
        assert result.id == user.id

    def test_raises_not_found_for_missing_id(self, organization):
        import uuid

        with pytest.raises(NotFound) as exc_info:
            user_selector.get_user_by_id(organization, uuid.uuid4())
        assert exc_info.value.code == "USER_NOT_FOUND"

    def test_raises_not_found_for_user_in_other_org(self, organization):
        other_user = UserFactory(organization=OrganizationFactory())
        with pytest.raises(NotFound):
            user_selector.get_user_by_id(organization, other_user.id)
