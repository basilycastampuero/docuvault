import pytest

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory


@pytest.fixture
def organization(db):
    return OrganizationFactory()


@pytest.fixture
def user(db, organization):
    return UserFactory(organization=organization)


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def org_admin(db, organization):
    from apps.authentication.models import UserRole

    return UserFactory(organization=organization, role=UserRole.ORG_ADMIN)
