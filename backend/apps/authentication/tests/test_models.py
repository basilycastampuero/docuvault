import pytest

from apps.authentication.models import User, UserRole
from apps.authentication.tests.factories import UserFactory


@pytest.mark.django_db
class TestUserModel:
    def test_creates_with_email(self):
        user = UserFactory()
        assert user.email is not None
        assert "@" in user.email

    def test_str_returns_email(self):
        user = UserFactory(email="alice@example.com")
        assert str(user) == "alice@example.com"

    def test_full_name_combines_first_last(self):
        user = UserFactory(first_name="Alice", last_name="Smith")
        assert user.full_name == "Alice Smith"

    def test_full_name_falls_back_to_email_when_blank(self):
        user = UserFactory(first_name="", last_name="")
        assert user.full_name == user.email

    def test_default_role_is_viewer(self):
        user = User.objects.create_user(email="viewer@example.com", password="pass")
        assert user.role == UserRole.VIEWER

    def test_is_active_by_default(self):
        user = UserFactory()
        assert user.is_active is True

    def test_email_is_unique(self):
        from django.db import IntegrityError

        UserFactory(email="dup@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="dup@example.com")

    def test_organization_can_be_null(self):
        user = User.objects.create_user(
            email="superadmin@example.com",
            password="pass",
            role=UserRole.SUPER_ADMIN,
        )
        assert user.organization is None

    def test_soft_delete_hides_from_objects(self):
        user = UserFactory()
        user_id = user.id
        user.soft_delete()
        assert not User.objects.filter(id=user_id).exists()
        assert User.all_objects.filter(id=user_id).exists()

    def test_restore_makes_visible_again(self):
        user = UserFactory()
        user.soft_delete()
        user.restore()
        assert User.objects.filter(id=user.id).exists()

    def test_create_superuser_sets_is_staff(self):
        user = User.objects.create_superuser(email="admin@example.com", password="pass")
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.role == UserRole.SUPER_ADMIN

    def test_user_belongs_to_organization(self, organization):
        user = UserFactory(organization=organization)
        user.refresh_from_db()
        assert user.organization == organization
