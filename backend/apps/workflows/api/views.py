import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.documents.selectors import get_document_by_id
from apps.permissions.permissions import HasRole, IsOrganizationMember
from apps.workflows.api.serializers import (
    WorkflowAdvanceSerializer,
    WorkflowExecutionSerializer,
    WorkflowStartSerializer,
    WorkflowStepLogSerializer,
    WorkflowTemplateCreateSerializer,
    WorkflowTemplateSerializer,
    WorkflowTemplateUpdateSerializer,
)
from apps.workflows.models import WorkflowStepAction
from apps.workflows.selectors import (
    get_execution_by_id,
    get_executions,
    get_step_logs,
    get_template_by_id,
    get_templates,
)
from apps.workflows.services import workflow_service

logger = logging.getLogger(__name__)

_ADMIN_ROLES = ["org_admin", "super_admin"]
_STARTER_ROLES = ["editor", "supervisor", "org_admin", "super_admin"]


def _require_roles(request: Request, roles: list[str]) -> None:
    """Raise PermissionDenied unless the request user has one of the given roles."""
    if not HasRole(*roles)().has_permission(request, None):
        raise PermissionDenied()


# ---------------------------------------------------------------------------
# Template views
# ---------------------------------------------------------------------------


@extend_schema(tags=["Workflows"])
class WorkflowTemplateListCreateView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="List workflow templates",
        responses=WorkflowTemplateSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        templates = get_templates(organization=request.organization)
        return Response(
            {"data": WorkflowTemplateSerializer(templates, many=True).data, "meta": {}}
        )

    @extend_schema(
        summary="Create a workflow template",
        request=WorkflowTemplateCreateSerializer,
        responses={201: WorkflowTemplateSerializer},
    )
    def post(self, request: Request) -> Response:
        _require_roles(request, _ADMIN_ROLES)
        serializer = WorkflowTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        template = workflow_service.create_template(
            organization=request.organization,
            user=request.user,
            name=data["name"],
            description=data["description"],
            steps=data["steps"],
            config=data["config"],
        )
        return Response(
            {"data": WorkflowTemplateSerializer(template).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve a workflow template",
        responses=WorkflowTemplateSerializer,
        tags=["Workflows"],
    ),
    patch=extend_schema(
        summary="Update a workflow template",
        request=WorkflowTemplateUpdateSerializer,
        responses=WorkflowTemplateSerializer,
        tags=["Workflows"],
    ),
    delete=extend_schema(
        summary="Delete a workflow template", responses={204: None}, tags=["Workflows"]
    ),
)
class WorkflowTemplateDetailView(APIView):
    permission_classes = [IsOrganizationMember]

    def get(self, request: Request, template_id) -> Response:
        template = get_template_by_id(
            organization=request.organization, template_id=template_id
        )
        return Response({"data": WorkflowTemplateSerializer(template).data})

    def patch(self, request: Request, template_id) -> Response:
        _require_roles(request, _ADMIN_ROLES)
        template = get_template_by_id(
            organization=request.organization, template_id=template_id
        )
        serializer = WorkflowTemplateUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = workflow_service.update_template(
            organization=request.organization,
            user=request.user,
            template=template,
            **serializer.validated_data,
        )
        return Response({"data": WorkflowTemplateSerializer(template).data})

    def delete(self, request: Request, template_id) -> Response:
        _require_roles(request, _ADMIN_ROLES)
        template = get_template_by_id(
            organization=request.organization, template_id=template_id
        )
        workflow_service.soft_delete_template(
            organization=request.organization, user=request.user, template=template
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Execution views
# ---------------------------------------------------------------------------


@extend_schema(tags=["Workflows"])
class WorkflowExecutionListCreateView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="List workflow executions",
        responses=WorkflowExecutionSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        document = None
        document_id = request.query_params.get("document")
        if document_id:
            document = get_document_by_id(
                organization=request.organization, document_id=document_id
            )
        qs = get_executions(
            organization=request.organization,
            document=document,
            status=request.query_params.get("status"),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            WorkflowExecutionSerializer(page, many=True).data
        )

    @extend_schema(
        summary="Start a workflow execution",
        request=WorkflowStartSerializer,
        responses={201: WorkflowExecutionSerializer},
    )
    def post(self, request: Request) -> Response:
        _require_roles(request, _STARTER_ROLES)
        serializer = WorkflowStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        document = get_document_by_id(
            organization=request.organization, document_id=data["document_id"]
        )
        template = get_template_by_id(
            organization=request.organization, template_id=data["template_id"]
        )
        execution = workflow_service.start_workflow(
            organization=request.organization,
            user=request.user,
            document=document,
            template=template,
        )
        return Response(
            {"data": WorkflowExecutionSerializer(execution).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Workflows"])
class WorkflowExecutionDetailView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Retrieve a workflow execution",
        responses=WorkflowExecutionSerializer,
    )
    def get(self, request: Request, execution_id) -> Response:
        execution = get_execution_by_id(
            organization=request.organization, execution_id=execution_id
        )
        return Response({"data": WorkflowExecutionSerializer(execution).data})


@extend_schema(tags=["Workflows"])
class WorkflowExecutionAdvanceView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="Advance a workflow execution (approve/reject/comment)",
        request=WorkflowAdvanceSerializer,
        responses=WorkflowExecutionSerializer,
    )
    def post(self, request: Request, execution_id) -> Response:
        execution = get_execution_by_id(
            organization=request.organization, execution_id=execution_id
        )
        serializer = WorkflowAdvanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        execution = workflow_service.advance_step(
            organization=request.organization,
            user=request.user,
            execution=execution,
            action=WorkflowStepAction(data["action"]),
            comment=data["comment"],
        )
        return Response({"data": WorkflowExecutionSerializer(execution).data})


@extend_schema(tags=["Workflows"])
class WorkflowExecutionLogsView(APIView):
    permission_classes = [IsOrganizationMember]

    @extend_schema(
        summary="List the step logs of a workflow execution",
        responses=WorkflowStepLogSerializer(many=True),
    )
    def get(self, request: Request, execution_id) -> Response:
        execution = get_execution_by_id(
            organization=request.organization, execution_id=execution_id
        )
        logs = get_step_logs(organization=request.organization, execution=execution)
        return Response(
            {"data": WorkflowStepLogSerializer(logs, many=True).data, "meta": {}}
        )
