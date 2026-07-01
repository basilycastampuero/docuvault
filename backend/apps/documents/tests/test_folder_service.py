import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError
from apps.documents.models import Folder
from apps.documents.services.folder_service import (
    create_folder,
    move_folder,
    rename_folder,
    soft_delete_folder,
)
from apps.organizations.tests.factories import OrganizationFactory

from .factories import DocumentFactory, FolderFactory


@pytest.mark.django_db
class TestCreateFolder:
    def test_creates_root_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = create_folder(organization=org, owner=user, name="Reports")
        assert folder.pk is not None
        assert folder.parent is None
        assert folder.organization == org

    def test_creates_child_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        parent = FolderFactory(organization=org, owner=user)
        child = create_folder(organization=org, owner=user, name="Sub", parent=parent)
        assert child.parent == parent

    def test_rejects_parent_from_other_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(organization=org1)
        other_parent = FolderFactory(organization=org2)
        with pytest.raises(PermissionDenied):
            create_folder(organization=org1, owner=user, name="X", parent=other_parent)

    def test_logs_audit_event(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = create_folder(organization=org, owner=user, name="Invoices")
        log = AuditLog.objects.get(
            organization=org, entity_type="folder", entity_id=str(folder.id)
        )
        assert log.action == AuditAction.CREATE


@pytest.mark.django_db
class TestRenameFolder:
    def test_renames_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org, name="Old")
        renamed = rename_folder(
            organization=org, user=user, folder=folder, new_name="New"
        )
        assert renamed.name == "New"

    def test_audit_contains_old_and_new_name(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org, name="OldName")
        rename_folder(organization=org, user=user, folder=folder, new_name="NewName")
        log = AuditLog.objects.filter(
            entity_type="folder", entity_id=str(folder.id), action=AuditAction.UPDATE
        ).first()
        assert log.old_values == {"name": "OldName"}
        assert log.new_values == {"name": "NewName"}


@pytest.mark.django_db
class TestMoveFolder:
    def test_moves_to_new_parent(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org)
        new_parent = FolderFactory(organization=org)
        moved = move_folder(
            organization=org, user=user, folder=folder, new_parent=new_parent
        )
        assert moved.parent == new_parent

    def test_moves_to_root(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        parent = FolderFactory(organization=org)
        folder = FolderFactory(organization=org, parent=parent)
        moved = move_folder(organization=org, user=user, folder=folder, new_parent=None)
        assert moved.parent is None

    def test_detects_direct_cycle(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        parent = FolderFactory(organization=org)
        child = FolderFactory(organization=org, parent=parent)
        # Moving parent into child would create a cycle
        with pytest.raises(ValidationError) as exc_info:
            move_folder(organization=org, user=user, folder=parent, new_parent=child)
        assert exc_info.value.code == "FOLDER_CYCLE"

    def test_detects_deep_cycle(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        a = FolderFactory(organization=org)
        b = FolderFactory(organization=org, parent=a)
        c = FolderFactory(organization=org, parent=b)
        with pytest.raises(ValidationError):
            move_folder(organization=org, user=user, folder=a, new_parent=c)

    def test_rejects_parent_from_other_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(organization=org1)
        folder = FolderFactory(organization=org1)
        other = FolderFactory(organization=org2)
        with pytest.raises(PermissionDenied):
            move_folder(organization=org1, user=user, folder=folder, new_parent=other)


@pytest.mark.django_db
class TestSoftDeleteFolder:
    def test_soft_deletes_empty_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org)
        soft_delete_folder(organization=org, user=user, folder=folder)
        assert Folder.objects.filter(pk=folder.pk).count() == 0
        assert Folder.all_objects.filter(pk=folder.pk).count() == 1

    def test_rejects_if_has_children(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        parent = FolderFactory(organization=org)
        FolderFactory(organization=org, parent=parent)
        with pytest.raises(ConflictError):
            soft_delete_folder(organization=org, user=user, folder=parent)

    def test_rejects_if_has_documents(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org)
        DocumentFactory(organization=org, folder=folder, created_by=user)
        with pytest.raises(ConflictError):
            soft_delete_folder(organization=org, user=user, folder=folder)

    def test_logs_audit_delete(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org, name="ToDelete")
        soft_delete_folder(organization=org, user=user, folder=folder)
        log = AuditLog.objects.get(
            entity_type="folder", entity_id=str(folder.id), action=AuditAction.DELETE
        )
        assert log.old_values["name"] == "ToDelete"
