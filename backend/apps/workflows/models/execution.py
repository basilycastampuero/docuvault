from django.db import models

from apps.core.models import BaseModel

from .enums import WorkflowStatus, WorkflowStepAction


class WorkflowExecution(BaseModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="workflow_executions",
    )
    template = models.ForeignKey(
        "workflows.WorkflowTemplate",
        on_delete=models.PROTECT,
        related_name="executions",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="workflow_executions",
    )
    current_step = models.ForeignKey(
        "workflows.WorkflowStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.PENDING,
    )
    started_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="started_workflows",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_executions"
        indexes = [
            models.Index(
                fields=["organization", "status"],
                name="idx_wf_exec_org_status",
            ),
            models.Index(
                fields=["organization", "document"],
                name="idx_wf_exec_org_document",
            ),
            models.Index(
                fields=["organization", "-created_at"],
                name="idx_wf_exec_org_created",
            ),
        ]
        constraints = [
            # Enforce "one active execution per document" at the DB level.
            # The service still does a friendly .exists() check, but this
            # partial unique index is what makes the rule race-proof.
            models.UniqueConstraint(
                fields=["document"],
                condition=models.Q(
                    status__in=["pending", "in_progress"],
                    deleted_at__isnull=True,
                ),
                name="uq_wf_exec_one_active_per_document",
            ),
        ]

    def __str__(self) -> str:
        return f"Execution {self.id} ({self.status})"


class WorkflowStepLog(BaseModel):
    execution = models.ForeignKey(
        "workflows.WorkflowExecution",
        on_delete=models.CASCADE,
        related_name="step_logs",
    )
    step = models.ForeignKey(
        "workflows.WorkflowStep",
        on_delete=models.PROTECT,
        related_name="+",
    )
    action = models.CharField(max_length=20, choices=WorkflowStepAction.choices)
    performed_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="workflow_actions",
    )
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "workflow_step_logs"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["execution", "created_at"],
                name="idx_wf_step_logs_exec_created",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.action} on {self.execution_id}"
