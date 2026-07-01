from django.db import models

from apps.authentication.models import UserRole
from apps.core.models import BaseModel


class WorkflowTemplate(BaseModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="workflow_templates",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workflow_templates"
        indexes = [
            models.Index(
                fields=["organization", "is_active"],
                name="idx_wf_templates_org_active",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_wf_templates_org_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name


class WorkflowStep(BaseModel):
    template = models.ForeignKey(
        "workflows.WorkflowTemplate",
        on_delete=models.CASCADE,
        related_name="steps",
    )
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField()
    required_role = models.CharField(max_length=20, choices=UserRole.choices)
    is_final = models.BooleanField(default=False)
    actions = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workflow_steps"
        ordering = ["order"]
        indexes = [
            models.Index(
                fields=["template", "order"],
                name="idx_wf_steps_template_order",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "order"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_wf_steps_template_order_alive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.template_id}:{self.order} {self.name}"
