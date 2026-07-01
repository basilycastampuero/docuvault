from typing import TYPE_CHECKING

from django.contrib.postgres.search import SearchQuery, SearchRank

from apps.documents.models import Document, DocumentStatus

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.documents.models import Folder
    from apps.organizations.models import Organization

MIN_QUERY_LENGTH = 2


def search_documents(
    organization: "Organization",
    query: str,
    folder: "Folder | None" = None,
    status: DocumentStatus | None = None,
) -> "QuerySet[Document]":
    """
    Full-text search over documents in an organization, ranked by relevance.

    Uses the pre-built search_vector (GIN-indexed). Documents with no vector
    yet (e.g. created before the signal was wired) will not appear; the data
    migration in this phase backfills them.
    """
    search_query = SearchQuery(query, config="simple", search_type="websearch")

    qs = (
        Document.objects.filter(
            organization=organization,
            search_vector=search_query,
        )
        .select_related("folder", "created_by")
        .annotate(rank=SearchRank("search_vector", search_query))
        .order_by("-rank", "-created_at")
    )

    if folder is not None:
        qs = qs.filter(folder=folder)

    if status is not None:
        qs = qs.filter(status=status)

    return qs
