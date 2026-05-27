import pytest

from apps.organizations.tests.factories import OrganizationFactory


@pytest.fixture
def organization(db):
    return OrganizationFactory()


@pytest.fixture
def inactive_organization(db):
    return OrganizationFactory(is_active=False)
