import logging

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.api.filters import AuditLogFilter
from apps.audit.api.serializers import AuditLogSerializer
from apps.audit.selectors import get_log_by_id, get_logs
from apps.core.pagination import StandardPagination
from apps.permissions.permissions import CanReadAuditLogs, IsOrganizationMember

logger = logging.getLogger(__name__)


@extend_schema(tags=["Audit"])
class AuditLogListView(APIView):
    permission_classes = [IsOrganizationMember, CanReadAuditLogs]

    @extend_schema(
        summary="List audit logs",
        responses=AuditLogSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        qs = get_logs(organization=request.organization)
        filterset = AuditLogFilter(request.query_params, queryset=qs)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(filterset.qs, request)
        return paginator.get_paginated_response(
            AuditLogSerializer(page, many=True).data
        )


@extend_schema(tags=["Audit"])
class AuditLogDetailView(APIView):
    permission_classes = [IsOrganizationMember, CanReadAuditLogs]

    @extend_schema(
        summary="Retrieve an audit log entry",
        responses=AuditLogSerializer,
    )
    def get(self, request: Request, log_id: int) -> Response:
        entry = get_log_by_id(organization=request.organization, log_id=log_id)
        return Response({"data": AuditLogSerializer(entry).data})
