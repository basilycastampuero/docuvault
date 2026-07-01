import factory

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.tests.factories import DocumentFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.workflows.models import (
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepAction,
    WorkflowStepLog,
    WorkflowTemplate,
)


class WorkflowTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowTemplate

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Template {n}")
    description = ""
    is_active = True
    config = factory.LazyFunction(dict)


class WorkflowStepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowStep

    template = factory.SubFactory(WorkflowTemplateFactory)
    name = factory.Sequence(lambda n: f"Step {n}")
    order = factory.Sequence(lambda n: n)
    required_role = UserRole.SUPERVISOR
    is_final = False
    actions = factory.LazyFunction(dict)


class WorkflowExecutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowExecution

    organization = factory.SubFactory(OrganizationFactory)
    template = factory.SubFactory(WorkflowTemplateFactory)
    document = factory.SubFactory(DocumentFactory)
    current_step = None
    status = WorkflowStatus.PENDING
    started_by = factory.SubFactory(UserFactory)


class WorkflowStepLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WorkflowStepLog

    execution = factory.SubFactory(WorkflowExecutionFactory)
    step = factory.SubFactory(WorkflowStepFactory)
    action = WorkflowStepAction.APPROVED
    performed_by = factory.SubFactory(UserFactory)
    comment = ""
