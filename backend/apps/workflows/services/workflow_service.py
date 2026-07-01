import logging
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import audit_service
from apps.authentication.models import UserRole
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError
from apps.documents.models import Document, DocumentStatus
from apps.workflows.models import (
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepAction,
    WorkflowStepLog,
    WorkflowTemplate,
)

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization

logger = logging.getLogger(__name__)

# Roles allowed to act on any step regardless of the step's required_role.
_ROLE_OVERRIDE = {UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN}

# Statuses that count as an active (in-flight) execution for a document.
_ACTIVE_STATUSES = [WorkflowStatus.PENDING, WorkflowStatus.IN_PROGRESS]


@transaction.atomic
def create_template(
    organization: "Organization",
    user: "User",
    name: str,
    description: str = "",
    steps: list[dict] | None = None,
    config: dict | None = None,
) -> WorkflowTemplate:
    """Create a workflow template with its ordered steps. Exactly one step must be final."""
    steps = steps or []
    if not steps:
        raise ValidationError(
            message="A workflow template must have at least one step.",
            code="WORKFLOW_NO_STEPS",
        )

    orders = [s["order"] for s in steps]
    if len(orders) != len(set(orders)):
        raise ValidationError(
            message="Workflow step orders must be unique.",
            code="WORKFLOW_DUPLICATE_ORDER",
        )

    final_count = sum(1 for s in steps if s.get("is_final"))
    if final_count != 1:
        raise ValidationError(
            message="A workflow template must have exactly one final step.",
            code="WORKFLOW_FINAL_STEP",
        )

    template = WorkflowTemplate.objects.create(
        organization=organization,
        name=name,
        description=description,
        config=config or {},
    )
    for step in steps:
        WorkflowStep.objects.create(
            template=template,
            name=step["name"],
            order=step["order"],
            required_role=step["required_role"],
            is_final=step.get("is_final", False),
            actions=step.get("actions", {}),
        )

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="workflow_template",
        entity_id=str(template.id),
        action=AuditAction.CREATE,
        new_values={"name": name, "steps": len(steps)},
    )
    logger.info("Workflow template created: %s (org=%s)", template.id, organization.id)
    return template


@transaction.atomic
def update_template(
    organization: "Organization",
    user: "User",
    template: WorkflowTemplate,
    name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> WorkflowTemplate:
    """Update a template's name, description or active flag. Steps are immutable here."""
    update_fields = ["updated_at"]
    old_values: dict = {}
    new_values: dict = {}

    if name is not None:
        old_values["name"] = template.name
        template.name = name
        new_values["name"] = name
        update_fields.append("name")
    if description is not None:
        old_values["description"] = template.description
        template.description = description
        new_values["description"] = description
        update_fields.append("description")
    if is_active is not None:
        old_values["is_active"] = template.is_active
        template.is_active = is_active
        new_values["is_active"] = is_active
        update_fields.append("is_active")

    if len(update_fields) > 1:
        template.save(update_fields=update_fields)
        audit_service.log(
            organization=organization,
            user=user,
            entity_type="workflow_template",
            entity_id=str(template.id),
            action=AuditAction.UPDATE,
            old_values=old_values,
            new_values=new_values,
        )
    return template


@transaction.atomic
def soft_delete_template(
    organization: "Organization",
    user: "User",
    template: WorkflowTemplate,
) -> None:
    """Soft-delete a template. Refuses if it has active executions."""
    has_active = WorkflowExecution.objects.filter(
        organization=organization,
        template=template,
        status__in=_ACTIVE_STATUSES,
    ).exists()
    if has_active:
        raise ConflictError(
            message="Cannot delete a template with active executions.",
            code="WORKFLOW_TEMPLATE_IN_USE",
        )

    template.soft_delete()
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="workflow_template",
        entity_id=str(template.id),
        action=AuditAction.DELETE,
        old_values={"name": template.name},
    )
    logger.info(
        "Workflow template soft-deleted: %s (org=%s)", template.id, organization.id
    )


@transaction.atomic
def start_workflow(
    organization: "Organization",
    user: "User",
    document: Document,
    template: WorkflowTemplate,
) -> WorkflowExecution:
    """Start a workflow execution for a document, moving it to under_review."""
    if template.organization_id != organization.pk:
        raise PermissionDenied("Template does not belong to this organization.")
    if document.organization_id != organization.pk:
        raise PermissionDenied("Document does not belong to this organization.")
    if not template.is_active:
        raise ConflictError(
            message="Cannot start an inactive workflow template.",
            code="WORKFLOW_TEMPLATE_INACTIVE",
        )

    has_active = WorkflowExecution.objects.filter(
        organization=organization,
        document=document,
        status__in=_ACTIVE_STATUSES,
    ).exists()
    if has_active:
        raise ConflictError(
            message="This document already has an active workflow execution.",
            code="WORKFLOW_ALREADY_ACTIVE",
        )

    first_step = template.steps.order_by("order").first()
    if first_step is None:
        raise ConflictError(
            message="Workflow template has no steps.",
            code="WORKFLOW_NO_STEPS",
        )

    # The .exists() check above is a fast, friendly path. The partial unique
    # constraint uq_wf_exec_one_active_per_document is the race-proof backstop:
    # if two requests pass the check concurrently, the DB rejects the loser and
    # we surface a clean 409 instead of a second active execution.
    try:
        with transaction.atomic():
            execution = WorkflowExecution.objects.create(
                organization=organization,
                template=template,
                document=document,
                current_step=first_step,
                status=WorkflowStatus.IN_PROGRESS,
                started_by=user,
                started_at=timezone.now(),
            )
    except IntegrityError:
        raise ConflictError(
            message="This document already has an active workflow execution.",
            code="WORKFLOW_ALREADY_ACTIVE",
        )

    _set_document_status(organization, user, document, DocumentStatus.UNDER_REVIEW)

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="workflow_execution",
        entity_id=str(execution.id),
        action=AuditAction.CREATE,
        new_values={
            "template_id": str(template.id),
            "document_id": str(document.id),
            "status": WorkflowStatus.IN_PROGRESS,
        },
    )

    # Notify users with the first step's required_role after the transaction commits.
    transaction.on_commit(
        lambda step=first_step, exec_=execution: _notify_step_assigned(
            organization, exec_, step
        )
    )

    logger.info(
        "Workflow started: execution=%s document=%s (org=%s)",
        execution.id,
        document.id,
        organization.id,
    )
    return execution


@transaction.atomic
def advance_step(
    organization: "Organization",
    user: "User",
    execution: WorkflowExecution,
    action: WorkflowStepAction,
    comment: str = "",
) -> WorkflowExecution:
    """
    Advance an in-progress execution by approving, rejecting or commenting on its
    current step. Approving the final step completes the workflow and approves the
    document; rejecting fails the workflow and rejects the document.
    """
    if execution.organization_id != organization.pk:
        raise PermissionDenied("Execution does not belong to this organization.")

    # Lock the execution row so two concurrent approvers cannot both read
    # IN_PROGRESS and double-advance. The status is then re-read under the lock.
    # of=("self",) locks only the execution row: current_step is a nullable FK
    # (LEFT JOIN) and Postgres forbids FOR UPDATE on the nullable side of a join.
    execution = (
        WorkflowExecution.objects.select_for_update(of=("self",))
        .select_related("template", "document", "current_step")
        .get(pk=execution.pk)
    )

    if execution.status != WorkflowStatus.IN_PROGRESS:
        raise ConflictError(
            message=f"Cannot advance an execution in status '{execution.status}'.",
            code="WORKFLOW_NOT_IN_PROGRESS",
        )

    step = execution.current_step
    if step is None:
        raise ConflictError(
            message="Execution has no current step.",
            code="WORKFLOW_NO_CURRENT_STEP",
        )

    if user.role != step.required_role and user.role not in _ROLE_OVERRIDE:
        raise PermissionDenied(
            f"Your role '{user.role}' cannot act on this step "
            f"(requires '{step.required_role}')."
        )

    WorkflowStepLog.objects.create(
        execution=execution,
        step=step,
        action=action,
        performed_by=user,
        comment=comment,
    )

    document = execution.document

    if action == WorkflowStepAction.REJECTED:
        execution.status = WorkflowStatus.REJECTED
        execution.current_step = None
        execution.completed_at = timezone.now()
        execution.save(
            update_fields=["status", "current_step", "completed_at", "updated_at"]
        )
        _set_document_status(organization, user, document, DocumentStatus.REJECTED)

    elif action == WorkflowStepAction.APPROVED:
        if step.is_final:
            execution.status = WorkflowStatus.COMPLETED
            execution.current_step = None
            execution.completed_at = timezone.now()
            execution.save(
                update_fields=["status", "current_step", "completed_at", "updated_at"]
            )
            _set_document_status(organization, user, document, DocumentStatus.APPROVED)
        else:
            next_step = (
                execution.template.steps.filter(order__gt=step.order)
                .order_by("order")
                .first()
            )
            execution.current_step = next_step
            execution.save(update_fields=["current_step", "updated_at"])

            if next_step is not None:
                # Notify users with the next step's required_role after commit.
                transaction.on_commit(
                    lambda s=next_step, exec_=execution: _notify_step_assigned(
                        organization, exec_, s
                    )
                )

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="workflow_execution",
        entity_id=str(execution.id),
        action=AuditAction.STATUS_CHANGE,
        old_values={"step_order": step.order},
        new_values={"action": action, "status": execution.status},
    )
    return execution


def reject_workflow(
    organization: "Organization",
    user: "User",
    execution: WorkflowExecution,
    reason: str = "",
) -> WorkflowExecution:
    """Reject a workflow execution. Sugar over advance_step(action=REJECTED)."""
    return advance_step(
        organization=organization,
        user=user,
        execution=execution,
        action=WorkflowStepAction.REJECTED,
        comment=reason,
    )


@transaction.atomic
def cancel_workflow(
    organization: "Organization",
    user: "User",
    execution: WorkflowExecution,
) -> WorkflowExecution:
    """Cancel an in-flight execution and return the document to draft."""
    if execution.organization_id != organization.pk:
        raise PermissionDenied("Execution does not belong to this organization.")
    if execution.status not in _ACTIVE_STATUSES:
        raise ConflictError(
            message=f"Cannot cancel an execution in status '{execution.status}'.",
            code="WORKFLOW_NOT_ACTIVE",
        )
    if execution.started_by_id != user.pk and user.role not in _ROLE_OVERRIDE:
        raise PermissionDenied("Only the initiator or an admin can cancel a workflow.")

    execution.status = WorkflowStatus.CANCELLED
    execution.current_step = None
    execution.completed_at = timezone.now()
    execution.save(
        update_fields=["status", "current_step", "completed_at", "updated_at"]
    )
    _set_document_status(organization, user, execution.document, DocumentStatus.DRAFT)

    audit_service.log(
        organization=organization,
        user=user,
        entity_type="workflow_execution",
        entity_id=str(execution.id),
        action=AuditAction.STATUS_CHANGE,
        new_values={"status": WorkflowStatus.CANCELLED},
    )
    return execution


def _notify_step_assigned(
    organization: "Organization",
    execution: WorkflowExecution,
    step: WorkflowStep,
) -> None:
    """Dispatch step-assigned notification. Import lazy to avoid circular import."""
    from apps.notifications.services import notification_service

    notification_service.notify_step_assigned(
        organization=organization,
        execution=execution,
        step=step,
    )


def _set_document_status(
    organization: "Organization",
    user: "User",
    document: Document,
    new_status: DocumentStatus,
) -> None:
    """
    Write the document status directly, bypassing the manual transition guard in
    document_service.change_document_status. The workflow engine is the only
    privileged path to approved/rejected (CLAUDE.md Phase 2 decision #3).
    """
    old_status = document.status
    document.status = new_status
    document.save(update_fields=["status", "updated_at"])
    audit_service.log(
        organization=organization,
        user=user,
        entity_type="document",
        entity_id=str(document.id),
        action=AuditAction.STATUS_CHANGE,
        old_values={"status": old_status},
        new_values={"status": new_status},
        metadata={"via": "workflow"},
    )
