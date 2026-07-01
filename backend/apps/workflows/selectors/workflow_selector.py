import uuid
from typing import TYPE_CHECKING

from apps.core.exceptions import NotFound
from apps.workflows.models import WorkflowExecution, WorkflowStepLog, WorkflowTemplate

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.documents.models import Document
    from apps.organizations.models import Organization


def get_templates(organization: "Organization") -> "QuerySet[WorkflowTemplate]":
    """Return all workflow templates for an organization with their steps prefetched."""
    return (
        WorkflowTemplate.objects.filter(organization=organization)
        .prefetch_related("steps")
        .order_by("name")
    )


def get_template_by_id(
    organization: "Organization", template_id: str | uuid.UUID
) -> WorkflowTemplate:
    """Return a template by id scoped to the organization. Raises NotFound otherwise."""
    try:
        return WorkflowTemplate.objects.prefetch_related("steps").get(
            id=template_id, organization=organization
        )
    except WorkflowTemplate.DoesNotExist:
        raise NotFound(f"Workflow template {template_id} not found.")


def get_executions(
    organization: "Organization",
    document: "Document | None" = None,
    status: str | None = None,
) -> "QuerySet[WorkflowExecution]":
    """Return a filtered queryset of workflow executions for the organization."""
    qs = (
        WorkflowExecution.objects.filter(organization=organization)
        .select_related("template", "document", "current_step", "started_by")
        .order_by("-created_at")
    )
    if document is not None:
        qs = qs.filter(document=document)
    if status is not None:
        qs = qs.filter(status=status)
    return qs


def get_execution_by_id(
    organization: "Organization", execution_id: str | uuid.UUID
) -> WorkflowExecution:
    """Return an execution by id scoped to the organization. Raises NotFound otherwise."""
    try:
        return WorkflowExecution.objects.select_related(
            "template", "document", "current_step", "started_by"
        ).get(id=execution_id, organization=organization)
    except WorkflowExecution.DoesNotExist:
        raise NotFound(f"Workflow execution {execution_id} not found.")


def get_step_logs(
    organization: "Organization", execution: WorkflowExecution
) -> "QuerySet[WorkflowStepLog]":
    """Return the step logs of an execution, oldest first."""
    return (
        WorkflowStepLog.objects.filter(execution=execution)
        .select_related("step", "performed_by")
        .order_by("created_at")
    )
