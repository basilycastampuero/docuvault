import pytest
from django.db import IntegrityError

from apps.authentication.models import UserRole
from apps.organizations.tests.factories import OrganizationFactory

from .factories import (
    WorkflowExecutionFactory,
    WorkflowStepFactory,
    WorkflowStepLogFactory,
    WorkflowTemplateFactory,
)


@pytest.mark.django_db
class TestWorkflowTemplateModel:
    def test_create_template(self):
        template = WorkflowTemplateFactory()
        assert template.pk is not None
        assert template.is_active is True
        assert template.deleted_at is None

    def test_unique_name_within_org_alive(self):
        org = OrganizationFactory()
        WorkflowTemplateFactory(organization=org, name="Approval")
        with pytest.raises(IntegrityError):
            WorkflowTemplateFactory(organization=org, name="Approval")

    def test_name_reusable_after_soft_delete(self):
        org = OrganizationFactory()
        t = WorkflowTemplateFactory(organization=org, name="Approval")
        t.soft_delete()
        WorkflowTemplateFactory(organization=org, name="Approval")  # no error

    def test_same_name_allowed_in_different_orgs(self):
        WorkflowTemplateFactory(organization=OrganizationFactory(), name="Approval")
        WorkflowTemplateFactory(organization=OrganizationFactory(), name="Approval")


@pytest.mark.django_db
class TestWorkflowStepModel:
    def test_steps_ordered_by_order(self):
        template = WorkflowTemplateFactory()
        WorkflowStepFactory(template=template, order=2, name="second")
        WorkflowStepFactory(template=template, order=1, name="first")
        names = list(template.steps.values_list("name", flat=True))
        assert names == ["first", "second"]

    def test_unique_order_within_template_alive(self):
        template = WorkflowTemplateFactory()
        WorkflowStepFactory(template=template, order=1)
        with pytest.raises(IntegrityError):
            WorkflowStepFactory(template=template, order=1)

    def test_required_role_accepts_user_role(self):
        step = WorkflowStepFactory(required_role=UserRole.EDITOR)
        assert step.required_role == UserRole.EDITOR


@pytest.mark.django_db
class TestWorkflowExecutionModel:
    def test_create_execution(self):
        execution = WorkflowExecutionFactory()
        assert execution.pk is not None
        assert execution.completed_at is None

    def test_tenant_scoping(self):
        org = OrganizationFactory()
        execution = WorkflowExecutionFactory(organization=org)
        assert execution.organization_id == org.id


@pytest.mark.django_db
class TestModelStr:
    def test_template_str(self):
        assert str(WorkflowTemplateFactory(name="Approval")) == "Approval"

    def test_step_str_contains_name(self):
        step = WorkflowStepFactory(name="Review", order=1)
        assert "Review" in str(step)

    def test_execution_str_contains_status(self):
        execution = WorkflowExecutionFactory()
        assert "pending" in str(execution)

    def test_step_log_str_contains_action(self):
        log = WorkflowStepLogFactory()
        assert "approved" in str(log)


@pytest.mark.django_db
class TestWorkflowStepLogModel:
    def test_logs_ordered_by_created_at(self):
        execution = WorkflowExecutionFactory()
        first = WorkflowStepLogFactory(execution=execution, comment="first")
        second = WorkflowStepLogFactory(execution=execution, comment="second")
        comments = list(execution.step_logs.values_list("comment", flat=True))
        assert comments == ["first", "second"]
        assert first.created_at <= second.created_at
