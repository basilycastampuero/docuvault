import pytest

from apps.core.exceptions import ConflictError
from apps.organizations.services import organization_service


@pytest.mark.django_db
class TestCreateOrganization:
    def test_creates_with_correct_name(self):
        org = organization_service.create_organization(name="Acme Corp")
        assert org.name == "Acme Corp"

    def test_auto_generates_slug_from_name(self):
        org = organization_service.create_organization(name="Acme Corp")
        assert org.slug == "acme-corp"

    def test_accepts_custom_slug(self):
        org = organization_service.create_organization(
            name="Acme Corp", slug="custom-slug"
        )
        assert org.slug == "custom-slug"

    def test_is_active_by_default(self):
        org = organization_service.create_organization(name="Acme Corp")
        assert org.is_active is True

    def test_duplicate_slug_raises_conflict(self):
        organization_service.create_organization(name="Acme Corp")
        with pytest.raises(ConflictError) as exc_info:
            organization_service.create_organization(
                name="Acme Corp 2", slug="acme-corp"
            )
        assert exc_info.value.code == "SLUG_TAKEN"

    def test_duplicate_auto_slug_raises_conflict(self):
        organization_service.create_organization(name="Acme Corp")
        with pytest.raises(ConflictError):
            organization_service.create_organization(name="Acme Corp")


@pytest.mark.django_db
class TestUpdateOrganization:
    def test_updates_name(self, organization):
        updated = organization_service.update_organization(
            organization, name="New Name"
        )
        assert updated.name == "New Name"

    def test_name_persisted_to_db(self, organization):
        organization_service.update_organization(organization, name="New Name")
        organization.refresh_from_db()
        assert organization.name == "New Name"

    def test_updates_settings(self, organization):
        organization_service.update_organization(
            organization, settings={"theme": "dark"}
        )
        organization.refresh_from_db()
        assert organization.settings == {"theme": "dark"}

    def test_slug_is_not_changed_by_name_update(self, organization):
        original_slug = organization.slug
        organization_service.update_organization(
            organization, name="Completely Different Name"
        )
        organization.refresh_from_db()
        assert organization.slug == original_slug

    def test_no_fields_does_not_raise(self, organization):
        updated = organization_service.update_organization(organization)
        assert updated is not None


@pytest.mark.django_db
class TestDeactivateOrganization:
    def test_sets_is_active_to_false(self, organization):
        assert organization.is_active is True
        organization_service.deactivate_organization(organization)
        organization.refresh_from_db()
        assert organization.is_active is False

    def test_does_not_soft_delete(self, organization):
        organization_service.deactivate_organization(organization)
        organization.refresh_from_db()
        assert organization.deleted_at is None

    def test_deactivated_org_still_visible_to_all_objects(self, organization):
        organization_service.deactivate_organization(organization)
        from apps.organizations.models import Organization

        assert Organization.all_objects.filter(id=organization.id).exists()
