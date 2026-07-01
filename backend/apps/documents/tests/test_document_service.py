import io
from unittest.mock import MagicMock, patch

import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import ConflictError, PermissionDenied
from apps.documents.models import Document, DocumentStatus, DocumentVersion
from apps.documents.services.document_service import (
    change_document_status,
    create_document,
    soft_delete_document,
    update_document_metadata,
    upload_new_version,
)
from apps.organizations.tests.factories import OrganizationFactory

from .factories import DocumentFactory, FolderFactory

PDF_HEADER = b"%PDF-1.4\n" + b"%" * 100


def _pdf_file(content: bytes = b"") -> io.BytesIO:
    return io.BytesIO(PDF_HEADER + content)


@pytest.fixture
def mock_storage(monkeypatch):
    """Mock StorageService so tests never touch MinIO."""
    from apps.documents.storage.storage_service import (
        StorageService as RealStorageService,
    )

    mock_instance = MagicMock()
    mock_instance.upload_file.return_value = "org/2026/01/doc/file.pdf"
    mock_class = MagicMock()
    mock_class.return_value = mock_instance
    mock_class.build_storage_path = RealStorageService.build_storage_path
    monkeypatch.setattr(
        "apps.documents.services.document_service.StorageService",
        mock_class,
    )
    # transaction=True tests fire on_commit; with CELERY_TASK_ALWAYS_EAGER the
    # OCR task runs synchronously and tries to reach MinIO (unavailable in CI).
    monkeypatch.setattr(
        "apps.documents.services.document_service.process_ocr.delay",
        MagicMock(),
    )
    return mock_instance


@pytest.mark.django_db(transaction=True)
class TestCreateDocument:
    def test_creates_document_with_version(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = create_document(
            organization=org, user=user, file=_pdf_file(), name="report.pdf"
        )
        assert doc.pk is not None
        assert doc.organization == org
        assert doc.created_by == user
        assert doc.status == DocumentStatus.DRAFT
        assert doc.version == 1
        assert DocumentVersion.objects.filter(document=doc, version_number=1).exists()

    def test_storage_upload_called(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        create_document(organization=org, user=user, file=_pdf_file(), name="f.pdf")
        mock_storage.upload_file.assert_called_once()

    def test_rejects_folder_from_other_org(self, mock_storage):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(organization=org1)
        folder = FolderFactory(organization=org2)
        with pytest.raises(PermissionDenied):
            create_document(
                organization=org1,
                user=user,
                file=_pdf_file(),
                name="x.pdf",
                folder=folder,
            )

    def test_rejects_oversized_file(self, mock_storage, settings):
        settings.MAX_UPLOAD_SIZE = 10
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        from apps.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            create_document(
                organization=org, user=user, file=io.BytesIO(b"x" * 100), name="big.pdf"
            )
        assert mock_storage.upload_file.call_count == 0
        assert Document.objects.filter(organization=org).count() == 0

    def test_audit_log_created(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = create_document(
            organization=org, user=user, file=_pdf_file(), name="a.pdf"
        )
        assert AuditLog.objects.filter(
            entity_type="document", entity_id=str(doc.id), action=AuditAction.CREATE
        ).exists()

    def test_on_commit_dispatches_ocr(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        with patch(
            "apps.documents.services.document_service.process_ocr.delay"
        ) as mock_delay:
            doc = create_document(
                organization=org, user=user, file=_pdf_file(), name="b.pdf"
            )
            mock_delay.assert_called_once_with(str(doc.id))

    def test_storage_upload_failure_rolls_back_document(self, mock_storage):
        """If storage.upload_file raises mid-transaction, no Document persists."""
        mock_storage.upload_file.side_effect = RuntimeError("S3 timeout")
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        with pytest.raises(RuntimeError):
            create_document(
                organization=org, user=user, file=_pdf_file(), name="fail.pdf"
            )
        assert Document.objects.filter(organization=org).count() == 0
        assert DocumentVersion.objects.count() == 0


@pytest.mark.django_db(transaction=True)
class TestUploadNewVersion:
    def test_increments_version(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = create_document(
            organization=org, user=user, file=_pdf_file(), name="d.pdf"
        )
        updated = upload_new_version(
            organization=org, user=user, document=doc, file=_pdf_file(b"v2")
        )
        assert updated.version == 2
        assert DocumentVersion.objects.filter(document=doc).count() == 2

    def test_preserves_original_version(self, mock_storage):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = create_document(
            organization=org, user=user, file=_pdf_file(), name="e.pdf"
        )
        upload_new_version(
            organization=org, user=user, document=doc, file=_pdf_file(b"v2")
        )
        assert DocumentVersion.objects.filter(document=doc, version_number=1).exists()
        assert DocumentVersion.objects.filter(document=doc, version_number=2).exists()


@pytest.mark.django_db
class TestUpdateDocumentMetadata:
    def test_updates_name(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, name="old.pdf")
        updated = update_document_metadata(
            organization=org, user=user, document=doc, name="new.pdf"
        )
        assert updated.name == "new.pdf"

    def test_updates_tags(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, tags=[])
        update_document_metadata(
            organization=org, user=user, document=doc, tags=["invoice", "2026"]
        )
        doc.refresh_from_db()
        assert doc.tags == ["invoice", "2026"]

    def test_audit_logged(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, name="before.pdf")
        update_document_metadata(
            organization=org, user=user, document=doc, name="after.pdf"
        )
        log = AuditLog.objects.filter(
            entity_type="document", entity_id=str(doc.id), action=AuditAction.UPDATE
        ).first()
        assert log is not None
        assert log.old_values["name"] == "before.pdf"


@pytest.mark.django_db
class TestChangeDocumentStatus:
    def test_draft_to_under_review(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        updated = change_document_status(org, user, doc, DocumentStatus.UNDER_REVIEW)
        assert updated.status == DocumentStatus.UNDER_REVIEW

    def test_under_review_to_draft(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.UNDER_REVIEW, created_by=user
        )
        updated = change_document_status(org, user, doc, DocumentStatus.DRAFT)
        assert updated.status == DocumentStatus.DRAFT

    def test_draft_to_approved_raises_conflict(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        with pytest.raises(ConflictError) as exc_info:
            change_document_status(org, user, doc, DocumentStatus.APPROVED)
        assert exc_info.value.code == "INVALID_STATUS_TRANSITION"

    def test_draft_to_rejected_raises_conflict(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        with pytest.raises(ConflictError):
            change_document_status(org, user, doc, DocumentStatus.REJECTED)

    def test_status_change_audit_logged(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, status=DocumentStatus.DRAFT, created_by=user
        )
        change_document_status(org, user, doc, DocumentStatus.UNDER_REVIEW)
        log = AuditLog.objects.filter(
            entity_type="document",
            entity_id=str(doc.id),
            action=AuditAction.STATUS_CHANGE,
        ).first()
        assert log is not None
        assert log.old_values["status"] == DocumentStatus.DRAFT


@pytest.mark.django_db
class TestSoftDeleteDocument:
    def test_soft_deletes(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user)
        soft_delete_document(organization=org, user=user, document=doc)
        assert Document.objects.filter(pk=doc.pk).count() == 0
        assert Document.all_objects.filter(pk=doc.pk).count() == 1

    def test_does_not_call_storage_delete(self, monkeypatch):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user)
        mock_storage = MagicMock()
        monkeypatch.setattr(
            "apps.documents.services.document_service.StorageService",
            lambda: mock_storage,
        )
        soft_delete_document(organization=org, user=user, document=doc)
        mock_storage.delete_file.assert_not_called()

    def test_audit_logged(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, name="todelete.pdf")
        soft_delete_document(organization=org, user=user, document=doc)
        log = AuditLog.objects.filter(
            entity_type="document", entity_id=str(doc.id), action=AuditAction.DELETE
        ).first()
        assert log is not None
        assert log.old_values["name"] == "todelete.pdf"
