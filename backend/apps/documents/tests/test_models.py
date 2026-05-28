import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.documents.models import Document, DocumentStatus, DocumentVersion
from apps.organizations.tests.factories import OrganizationFactory

from .factories import DocumentFactory, DocumentVersionFactory, FolderFactory


@pytest.mark.django_db
class TestFolderModel:
    def test_create_folder(self):
        folder = FolderFactory()
        assert folder.pk is not None
        assert folder.deleted_at is None

    def test_folder_with_parent(self):
        org = OrganizationFactory()
        parent = FolderFactory(organization=org)
        child = FolderFactory(organization=org, parent=parent)
        assert child.parent == parent

    def test_folder_cannot_be_own_parent(self):
        folder = FolderFactory()
        folder.parent_id = folder.pk
        with pytest.raises(ValidationError):
            folder.clean()

    def test_unique_name_within_same_parent_alive(self):
        org = OrganizationFactory()
        parent = FolderFactory(organization=org)
        FolderFactory(organization=org, parent=parent, name="Reports")
        with pytest.raises(IntegrityError):
            FolderFactory(organization=org, parent=parent, name="Reports")

    def test_unique_name_allows_reuse_after_soft_delete(self):
        org = OrganizationFactory()
        parent = FolderFactory(organization=org)
        f = FolderFactory(organization=org, parent=parent, name="Reports")
        f.soft_delete()
        # Should not raise — deleted folder frees the unique slot
        FolderFactory(organization=org, parent=parent, name="Reports")

    def test_same_name_allowed_in_different_parents(self):
        org = OrganizationFactory()
        parent1 = FolderFactory(organization=org)
        parent2 = FolderFactory(organization=org)
        FolderFactory(organization=org, parent=parent1, name="Reports")
        FolderFactory(organization=org, parent=parent2, name="Reports")  # no error

    def test_soft_delete_marks_deleted_at(self):
        folder = FolderFactory()
        folder.soft_delete()
        assert folder.deleted_at is not None
        assert folder.is_deleted

    def test_str(self):
        folder = FolderFactory(name="My Folder")
        assert str(folder) == "My Folder"


@pytest.mark.django_db
class TestDocumentModel:
    def test_create_document(self):
        doc = DocumentFactory()
        assert doc.pk is not None
        assert doc.status == DocumentStatus.DRAFT
        assert doc.version == 1

    def test_document_default_status_is_draft(self):
        doc = DocumentFactory()
        assert doc.status == DocumentStatus.DRAFT

    def test_unique_name_within_folder_alive(self):
        org = OrganizationFactory()
        folder = FolderFactory(organization=org)
        DocumentFactory(organization=org, folder=folder, name="report.pdf")
        with pytest.raises(IntegrityError):
            DocumentFactory(organization=org, folder=folder, name="report.pdf")

    def test_unique_name_allows_reuse_after_soft_delete(self):
        org = OrganizationFactory()
        folder = FolderFactory(organization=org)
        doc = DocumentFactory(organization=org, folder=folder, name="report.pdf")
        doc.soft_delete()
        DocumentFactory(organization=org, folder=folder, name="report.pdf")

    def test_soft_delete(self):
        doc = DocumentFactory()
        doc.soft_delete()
        assert doc.is_deleted
        assert Document.objects.filter(pk=doc.pk).count() == 0
        assert Document.all_objects.filter(pk=doc.pk).count() == 1

    def test_str(self):
        doc = DocumentFactory(name="contract.pdf")
        assert str(doc) == "contract.pdf"


@pytest.mark.django_db
class TestDocumentVersionModel:
    def test_create_version(self):
        ver = DocumentVersionFactory(version_number=1)
        assert ver.pk is not None

    def test_versions_ordered_descending(self):
        doc = DocumentFactory()
        DocumentVersionFactory(document=doc, version_number=1)
        DocumentVersionFactory(document=doc, version_number=2)
        DocumentVersionFactory(document=doc, version_number=3)
        versions = list(DocumentVersion.objects.filter(document=doc))
        assert [v.version_number for v in versions] == [3, 2, 1]

    def test_unique_version_number_per_document(self):
        doc = DocumentFactory()
        DocumentVersionFactory(document=doc, version_number=1)
        with pytest.raises(IntegrityError):
            DocumentVersionFactory(document=doc, version_number=1)

    def test_str(self):
        ver = DocumentVersionFactory(version_number=2)
        assert "v2" in str(ver)
