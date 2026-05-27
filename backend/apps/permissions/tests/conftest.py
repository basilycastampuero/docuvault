import pytest

from apps.authentication.tests.factories import UserFactory
from apps.organizations.tests.factories import OrganizationFactory


@pytest.fixture
def organization(db):
    return OrganizationFactory()


@pytest.fixture
def user(db, organization):
    return UserFactory(organization=organization)
