import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.documents.models import DocumentStatus
from apps.documents.selectors.folder_selector import get_folder_by_id
from apps.permissions.permissions import IsOrganizationMember
from apps.search.api.serializers import SearchQuerySerializer, SearchResultSerializer
from apps.search.selectors.search_selector import search_documents

logger = logging.getLogger(__name__)


@extend_schema(tags=["Search"])
class DocumentSearchView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Full-text search over documents",
        description=(
            "Search documents by content using PostgreSQL full-text search. "
            "Results are ranked by relevance. Supports multi-word queries and "
            'quoted phrases (e.g. `"exact phrase"`). '
            "Minimum query length: 2 characters."
        ),
        parameters=[
            OpenApiParameter(
                name="q",
                description="Search query (min 2 chars). Supports websearch syntax.",
                required=True,
                type=OpenApiTypes.STR,
            ),
            OpenApiParameter(
                name="folder",
                description="Filter results to a specific folder (UUID).",
                required=False,
                type=OpenApiTypes.UUID,
            ),
            OpenApiParameter(
                name="status",
                description="Filter by document status.",
                required=False,
                enum=[s.value for s in DocumentStatus],
                type=OpenApiTypes.STR,
            ),
        ],
        responses=SearchResultSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        params = SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        folder = None
        if data["folder"] is not None:
            folder = get_folder_by_id(
                organization=request.organization,
                folder_id=data["folder"],
            )

        qs = search_documents(
            organization=request.organization,
            query=data["q"],
            folder=folder,
            status=data["status"],
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            SearchResultSerializer(page, many=True).data
        )
