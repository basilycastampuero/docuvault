import pytest
from django.contrib.postgres.search import SearchQuery
from rest_framework.test import APIClient

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.models import Document, DocumentStatus
from apps.documents.tests.factories import DocumentFactory, FolderFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.search.selectors.search_selector import search_documents

SEARCH_URL = "/api/v1/search/"
LOGIN_URL = "/api/v1/auth/login/"


def _client_for(user) -> APIClient:
    client = APIClient()
    response = client.post(LOGIN_URL, {"email": user.email, "password": "testpass123"})
    token = response.data["data"]["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


# ---------------------------------------------------------------------------
# Signal tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSearchVectorSignal:
    def test_search_vector_populated_on_create(self):
        """search_vector is built synchronously after document creation."""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, created_by=user, name="quarterly report"
        )

        doc.refresh_from_db()
        assert doc.search_vector is not None
        assert Document.objects.filter(
            pk=doc.pk,
            search_vector=SearchQuery("quarterly", config="simple"),
        ).exists()

    def test_search_vector_updated_on_name_change(self):
        """Saving a new name rebuilds search_vector to reflect the change."""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, name="old title")

        doc.name = "budget forecast"
        doc.save(update_fields=["name", "updated_at"])

        assert Document.objects.filter(
            pk=doc.pk,
            search_vector=SearchQuery("forecast", config="simple"),
        ).exists()
        assert not Document.objects.filter(
            pk=doc.pk,
            search_vector=SearchQuery("old", config="simple"),
        ).exists()

    def test_search_vector_includes_tags(self):
        """Tags are joined and indexed with weight C."""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, created_by=user, tags=["invoice", "finance"]
        )

        assert Document.objects.filter(
            pk=doc.pk,
            search_vector=SearchQuery("invoice", config="simple"),
        ).exists()

    def test_non_text_save_skips_rebuild_but_keeps_searchable(
        self, django_assert_num_queries
    ):
        """
        A save touching only non-searchable fields (e.g. status) must not waste
        a rebuild, yet the document stays searchable from its original content.
        """
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user, name="Tax Statement")

        # Status-only save: the signal guard should skip the rebuild UPDATE.
        with django_assert_num_queries(1):  # only the status UPDATE, no extra
            doc.status = DocumentStatus.UNDER_REVIEW
            doc.save(update_fields=["status", "updated_at"])

        assert Document.objects.filter(
            pk=doc.pk,
            search_vector=SearchQuery("tax", config="simple"),
        ).exists()


# ---------------------------------------------------------------------------
# Selector tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSearchSelector:
    def test_finds_document_by_name(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org, created_by=user, name="Annual Report 2026"
        )
        DocumentFactory(organization=org, created_by=user, name="January Invoice")

        results = list(search_documents(organization=org, query="annual"))
        assert len(results) == 1
        assert results[0].id == doc.id

    def test_finds_document_by_description(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(
            organization=org,
            created_by=user,
            description="summary of financial projections",
        )
        DocumentFactory(organization=org, created_by=user, description="meeting notes")

        results = list(search_documents(organization=org, query="projections"))
        assert len(results) == 1
        assert results[0].id == doc.id

    def test_name_match_ranks_above_description_match(self):
        """Weight A (name) should rank higher than weight B (description)."""
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        desc_match = DocumentFactory(
            organization=org,
            created_by=user,
            name="Plain Document",
            description="contract details here",
        )
        name_match = DocumentFactory(
            organization=org,
            created_by=user,
            name="Contract Agreement",
            description="",
        )

        results = list(search_documents(organization=org, query="contract"))
        assert len(results) == 2
        assert results[0].id == name_match.id
        assert results[1].id == desc_match.id

    def test_tenant_isolation(self):
        """Org A cannot see org B's documents in search results."""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = UserFactory(organization=org_a)
        user_b = UserFactory(organization=org_b)
        DocumentFactory(organization=org_a, created_by=user_a, name="Shared Term")
        DocumentFactory(organization=org_b, created_by=user_b, name="Shared Term")

        results_a = list(search_documents(organization=org_a, query="shared"))
        results_b = list(search_documents(organization=org_b, query="shared"))
        assert len(results_a) == 1
        assert len(results_b) == 1
        assert results_a[0].organization_id == org_a.id
        assert results_b[0].organization_id == org_b.id

    def test_filter_by_status(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        DocumentFactory(
            organization=org,
            created_by=user,
            name="Contract Draft",
            status=DocumentStatus.DRAFT,
        )
        DocumentFactory(
            organization=org,
            created_by=user,
            name="Contract Review",
            status=DocumentStatus.UNDER_REVIEW,
        )

        results = list(
            search_documents(
                organization=org, query="contract", status=DocumentStatus.DRAFT
            )
        )
        assert len(results) == 1
        assert results[0].status == DocumentStatus.DRAFT

    def test_filter_by_folder(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        folder = FolderFactory(organization=org)
        doc_in = DocumentFactory(
            organization=org, created_by=user, folder=folder, name="Budget Proposal"
        )
        DocumentFactory(
            organization=org, created_by=user, folder=None, name="Budget Global"
        )

        results = list(
            search_documents(organization=org, query="budget", folder=folder)
        )
        assert len(results) == 1
        assert results[0].id == doc_in.id

    def test_no_n_plus_one(self, django_assert_num_queries):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        for i in range(10):
            DocumentFactory(organization=org, created_by=user, name=f"Report {i}")

        with django_assert_num_queries(1):
            list(search_documents(organization=org, query="report"))


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSearchAPI:
    def test_q_required_returns_400(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.VIEWER)
        client = _client_for(user)

        response = client.get(SEARCH_URL)
        assert response.status_code == 400

    def test_q_too_short_returns_400(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.VIEWER)
        client = _client_for(user)

        response = client.get(SEARCH_URL, {"q": "a"})
        assert response.status_code == 400

    def test_unauthenticated_returns_401(self):
        response = APIClient().get(SEARCH_URL, {"q": "test"})
        assert response.status_code == 401

    def test_any_member_can_search(self):
        """VIEWER role (lowest) can still search — no elevated role required."""
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.VIEWER)
        DocumentFactory(organization=org, created_by=user, name="Visible Document")
        client = _client_for(user)

        response = client.get(SEARCH_URL, {"q": "visible"})
        assert response.status_code == 200

    def test_response_envelope_and_pagination(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.EDITOR)
        for i in range(3):
            DocumentFactory(organization=org, created_by=user, name=f"Report {i}")
        client = _client_for(user)

        response = client.get(SEARCH_URL, {"q": "report"})
        assert response.status_code == 200
        assert "data" in response.data
        assert "meta" in response.data
        assert response.data["meta"]["count"] == 3
        assert len(response.data["data"]) == 3

    def test_results_include_rank(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.VIEWER)
        DocumentFactory(organization=org, created_by=user, name="Contract Review")
        client = _client_for(user)

        response = client.get(SEARCH_URL, {"q": "contract"})
        assert response.status_code == 200
        assert "rank" in response.data["data"][0]

    def test_filter_by_status(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org, role=UserRole.VIEWER)
        DocumentFactory(
            organization=org,
            created_by=user,
            name="Invoice Draft",
            status=DocumentStatus.DRAFT,
        )
        DocumentFactory(
            organization=org,
            created_by=user,
            name="Invoice Review",
            status=DocumentStatus.UNDER_REVIEW,
        )
        client = _client_for(user)

        response = client.get(SEARCH_URL, {"q": "invoice", "status": "draft"})
        assert response.status_code == 200
        assert response.data["meta"]["count"] == 1
        assert response.data["data"][0]["status"] == "draft"

    def test_tenant_isolation(self):
        """User from org A cannot retrieve org B's documents via search."""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        user_a = UserFactory(organization=org_a, role=UserRole.VIEWER)
        user_b = UserFactory(organization=org_b)
        DocumentFactory(organization=org_b, created_by=user_b, name="Secret Document")
        client = _client_for(user_a)

        response = client.get(SEARCH_URL, {"q": "secret"})
        assert response.status_code == 200
        assert response.data["meta"]["count"] == 0
