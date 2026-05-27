import pytest

from apps.authentication.models import UserRole
from apps.authentication.services import user_service
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError


@pytest.mark.django_db
class TestCreateUser:
    def test_creates_user_in_organization(self, organization, org_admin):
        user = user_service.create_user(
            organization=organization,
            email="new@example.com",
            role=UserRole.EDITOR,
        )
        assert user.organization == organization
        assert user.email == "new@example.com"
        assert user.role == UserRole.EDITOR

    def test_duplicate_email_raises_conflict(self, organization, org_admin):
        UserFactory(organization=organization, email="taken@example.com")
        with pytest.raises(ConflictError) as exc_info:
            user_service.create_user(
                organization=organization,
                email="taken@example.com",
                role=UserRole.VIEWER,
            )
        assert exc_info.value.code == "EMAIL_TAKEN"

    def test_super_admin_role_raises_validation_error(self, organization):
        with pytest.raises(ValidationError) as exc_info:
            user_service.create_user(
                organization=organization,
                email="admin@example.com",
                role=UserRole.SUPER_ADMIN,
            )
        assert exc_info.value.code == "INVALID_ROLE"

    def test_user_is_active_by_default(self, organization):
        user = user_service.create_user(
            organization=organization,
            email="active@example.com",
            role=UserRole.VIEWER,
        )
        assert user.is_active is True

    def test_password_is_optional(self, organization):
        user = user_service.create_user(
            organization=organization,
            email="nopass@example.com",
            role=UserRole.VIEWER,
        )
        assert not user.has_usable_password()


@pytest.mark.django_db
class TestUpdateUser:
    def test_updates_first_and_last_name(self, organization, org_admin):
        user = UserFactory(organization=organization)
        updated = user_service.update_user(
            organization=organization,
            user=user,
            requesting_user=org_admin,
            first_name="Alice",
            last_name="Smith",
        )
        assert updated.first_name == "Alice"
        assert updated.last_name == "Smith"

    def test_updates_role(self, organization, org_admin):
        user = UserFactory(organization=organization, role=UserRole.VIEWER)
        updated = user_service.update_user(
            organization=organization,
            user=user,
            requesting_user=org_admin,
            role=UserRole.EDITOR,
        )
        assert updated.role == UserRole.EDITOR

    def test_user_cannot_change_own_role(self, organization, org_admin):
        with pytest.raises(PermissionDenied) as exc_info:
            user_service.update_user(
                organization=organization,
                user=org_admin,
                requesting_user=org_admin,
                role=UserRole.SUPER_ADMIN,
            )
        assert exc_info.value.code == "CANNOT_CHANGE_OWN_ROLE"

    def test_super_admin_role_raises_validation_error(self, organization, org_admin):
        user = UserFactory(organization=organization)
        with pytest.raises(ValidationError) as exc_info:
            user_service.update_user(
                organization=organization,
                user=user,
                requesting_user=org_admin,
                role=UserRole.SUPER_ADMIN,
            )
        assert exc_info.value.code == "INVALID_ROLE"

    def test_changes_persisted_to_db(self, organization, org_admin):
        user = UserFactory(organization=organization)
        user_service.update_user(
            organization=organization,
            user=user,
            requesting_user=org_admin,
            first_name="Persisted",
        )
        user.refresh_from_db()
        assert user.first_name == "Persisted"


@pytest.mark.django_db
class TestDeactivateUser:
    def test_sets_is_active_to_false(self, organization, org_admin):
        user = UserFactory(organization=organization)
        user_service.deactivate_user(
            organization=organization, user=user, requesting_user=org_admin
        )
        user.refresh_from_db()
        assert user.is_active is False

    def test_user_cannot_deactivate_self(self, organization, org_admin):
        with pytest.raises(PermissionDenied) as exc_info:
            user_service.deactivate_user(
                organization=organization,
                user=org_admin,
                requesting_user=org_admin,
            )
        assert exc_info.value.code == "CANNOT_DEACTIVATE_SELF"

    def test_deactivated_user_is_not_soft_deleted(self, organization, org_admin):
        from apps.authentication.models import User

        user = UserFactory(organization=organization)
        user_service.deactivate_user(
            organization=organization, user=user, requesting_user=org_admin
        )
        assert User.objects.filter(id=user.id).exists()
        assert user.deleted_at is None
