import pytest

from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import NotFound
from apps.documents.models import DocumentStatus
from apps.documents.selectors.document_selector import (
    get_document_by_id,
    get_document_versions,
    get_documents,
)
from apps.organizations.tests.factories import OrganizationFactory

from .factories import DocumentFactory, DocumentVersionFactory, FolderFactory


@pytest.mark.django_db
class TestDocumentSelector:
    def test_get_document_by_id(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user)
        result = get_document_by_id(organization=org, document_id=doc.id)
        assert result == doc

    def test_get_document_by_id_wrong_org_raises(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(organization=org2)
        doc = DocumentFactory(organization=org2, created_by=user)
        with pytest.raises(NotFound):
            get_document_by_id(organization=org1, document_id=doc.id)

    def test_get_documents_tenant_isolation(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user1 = UserFactory(organization=org1)
        user2 = UserFactory(organization=org2)
        DocumentFactory(organization=org1, created_by=user1)
        DocumentFactory(organization=org2, created_by=user2)
        assert get_documents(org1).count() == 1
        assert get_documents(org2).count() == 1

    def test_get_documents_filter_by_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org)
        doc_in = DocumentFactory(organization=org, folder=folder, created_by=user)
        DocumentFactory(organization=org, folder=None, created_by=user)
        qs = get_documents(org, folder=folder)
        assert qs.count() == 1
        assert qs.first() == doc_in

    def test_get_documents_filter_by_status(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        DocumentFactory(organization=org, status=DocumentStatus.DRAFT, created_by=user)
        DocumentFactory(
            organization=org, status=DocumentStatus.UNDER_REVIEW, created_by=user
        )
        assert get_documents(org, status=DocumentStatus.DRAFT).count() == 1

    def test_get_documents_filter_by_tags(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        DocumentFactory(organization=org, tags=["invoice"], created_by=user)
        DocumentFactory(organization=org, tags=["contract"], created_by=user)
        assert get_documents(org, tags=["invoice"]).count() == 1

    def test_get_documents_filter_by_search(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        DocumentFactory(organization=org, name="annual_report.pdf", created_by=user)
        DocumentFactory(organization=org, name="invoice_jan.pdf", created_by=user)
        assert get_documents(org, search="annual").count() == 1

    def test_get_documents_no_n_plus_one(self, django_assert_num_queries):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        for _ in range(10):
            DocumentFactory(organization=org, created_by=user)
        with django_assert_num_queries(1):
            list(get_documents(organization=org))

    def test_get_document_versions(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user)
        DocumentVersionFactory(document=doc, version_number=1, created_by=user)
        DocumentVersionFactory(document=doc, version_number=2, created_by=user)
        versions = list(get_document_versions(org, doc))
        assert [v.version_number for v in versions] == [2, 1]
