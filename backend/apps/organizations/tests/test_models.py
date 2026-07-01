import pytest

from apps.organizations.models import Organization
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestOrganizationModel:
    def test_str_returns_name(self, organization):
        assert str(organization) == organization.name

    def test_default_is_active(self, db):
        org = OrganizationFactory()
        assert org.is_active is True

    def test_default_settings_is_empty_dict(self, db):
        org = OrganizationFactory()
        assert org.settings == {}

    def test_slug_is_unique(self, organization):
        with pytest.raises(Exception):
            OrganizationFactory(slug=organization.slug)

    def test_soft_delete_hides_from_default_manager(self, organization):
        org_id = organization.id
        organization.soft_delete()

        assert not Organization.objects.filter(id=org_id).exists()
        assert Organization.all_objects.filter(id=org_id).exists()

    def test_soft_delete_sets_deleted_at(self, organization):
        assert organization.deleted_at is None
        organization.soft_delete()
        assert organization.deleted_at is not None
        assert organization.is_deleted is True

    def test_restore_clears_deleted_at(self, organization):
        organization.soft_delete()
        organization.restore()

        assert organization.deleted_at is None
        assert organization.is_deleted is False
        assert Organization.objects.filter(id=organization.id).exists()
