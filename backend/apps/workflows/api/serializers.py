from rest_framework import serializers

from apps.authentication.models import UserRole
from apps.workflows.models import (
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepAction,
    WorkflowStepLog,
    WorkflowTemplate,
)

# ---------------------------------------------------------------------------
# Read serializers
# ---------------------------------------------------------------------------


class WorkflowStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStep
        fields = ["id", "name", "order", "required_role", "is_final", "actions"]
        read_only_fields = fields


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    steps = WorkflowStepSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowTemplate
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "config",
            "steps",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    document_name = serializers.CharField(source="document.name", read_only=True)
    current_step = WorkflowStepSerializer(read_only=True)
    started_by_email = serializers.CharField(source="started_by.email", read_only=True)

    class Meta:
        model = WorkflowExecution
        fields = [
            "id",
            "template",
            "template_name",
            "document",
            "document_name",
            "current_step",
            "status",
            "started_by_email",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class WorkflowStepLogSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source="step.name", read_only=True)
    step_order = serializers.IntegerField(source="step.order", read_only=True)
    performed_by_email = serializers.CharField(
        source="performed_by.email", read_only=True
    )

    class Meta:
        model = WorkflowStepLog
        fields = [
            "id",
            "step_name",
            "step_order",
            "action",
            "performed_by_email",
            "comment",
            "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Write serializers
# ---------------------------------------------------------------------------


class WorkflowStepCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    order = serializers.IntegerField(min_value=0)
    required_role = serializers.ChoiceField(choices=UserRole.choices)
    is_final = serializers.BooleanField(default=False)
    actions = serializers.DictField(required=False, default=dict)


class WorkflowTemplateCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    config = serializers.DictField(required=False, default=dict)
    steps = WorkflowStepCreateSerializer(many=True)


class WorkflowTemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class WorkflowStartSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    template_id = serializers.UUIDField()


class WorkflowAdvanceSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=WorkflowStepAction.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class WorkflowStartFromDocumentSerializer(serializers.Serializer):
    """Used by DocumentStartWorkflowView to start a workflow from a document detail page."""

    template_id = serializers.UUIDField()
