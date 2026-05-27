import uuid

import pytest

from apps.core.exceptions import NotFound
from apps.organizations.selectors import organization_selector
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestGetById:
    def test_returns_organization(self, organization):
        result = organization_selector.get_by_id(organization.id)
        assert result == organization

    def test_raises_not_found_for_unknown_id(self):
        with pytest.raises(NotFound):
            organization_selector.get_by_id(uuid.uuid4())

    def test_raises_not_found_for_soft_deleted(self, organization):
        organization.soft_delete()
        with pytest.raises(NotFound):
            organization_selector.get_by_id(organization.id)


@pytest.mark.django_db
class TestGetBySlug:
    def test_returns_organization(self, organization):
        result = organization_selector.get_by_slug(organization.slug)
        assert result == organization

    def test_raises_not_found_for_unknown_slug(self):
        with pytest.raises(NotFound):
            organization_selector.get_by_slug("does-not-exist")

    def test_raises_not_found_for_soft_deleted(self, organization):
        organization.soft_delete()
        with pytest.raises(NotFound):
            organization_selector.get_by_slug(organization.slug)


@pytest.mark.django_db
class TestGetAllActive:
    def test_returns_active_organizations(self, organization):
        results = list(organization_selector.get_all_active())
        assert organization in results

    def test_excludes_inactive_organizations(self, inactive_organization):
        results = list(organization_selector.get_all_active())
        assert inactive_organization not in results

    def test_excludes_soft_deleted_organizations(self, organization):
        organization.soft_delete()
        results = list(organization_selector.get_all_active())
        assert organization not in results

    def test_returns_multiple_active(self, db):
        orgs = OrganizationFactory.create_batch(3)
        OrganizationFactory(is_active=False)
        results = list(organization_selector.get_all_active())
        for org in orgs:
            assert org in results
        assert len(results) == 3
