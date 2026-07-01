import pytest

from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import NotFound
from apps.documents.tests.factories import DocumentFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.workflows.models import WorkflowStatus
from apps.workflows.selectors import (
    get_execution_by_id,
    get_executions,
    get_template_by_id,
    get_templates,
)

from .factories import (
    WorkflowExecutionFactory,
    WorkflowStepFactory,
    WorkflowTemplateFactory,
)


@pytest.mark.django_db
class TestTemplateSelectors:
    def test_get_templates_tenant_isolation(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        WorkflowTemplateFactory(organization=org_a)
        WorkflowTemplateFactory(organization=org_b)
        assert get_templates(organization=org_a).count() == 1

    def test_get_templates_prefetches_steps(self, django_assert_num_queries):
        org = OrganizationFactory()
        t = WorkflowTemplateFactory(organization=org)
        WorkflowStepFactory(template=t, order=1)
        WorkflowStepFactory(template=t, order=2)

        # 1 query for templates + 1 for the prefetched steps
        with django_assert_num_queries(2):
            templates = list(get_templates(organization=org))
            for tmpl in templates:
                list(tmpl.steps.all())

    def test_get_template_by_id_other_org_not_found(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        t = WorkflowTemplateFactory(organization=org_a)
        with pytest.raises(NotFound):
            get_template_by_id(organization=org_b, template_id=t.id)


@pytest.mark.django_db
class TestExecutionSelectors:
    def test_get_executions_no_n_plus_one(self, django_assert_num_queries):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        for _ in range(3):
            WorkflowExecutionFactory(organization=org, started_by=user)

        with django_assert_num_queries(1):
            list(get_executions(organization=org))

    def test_get_executions_filter_by_status(self):
        org = OrganizationFactory()
        WorkflowExecutionFactory(organization=org, status=WorkflowStatus.IN_PROGRESS)
        WorkflowExecutionFactory(organization=org, status=WorkflowStatus.COMPLETED)
        qs = get_executions(organization=org, status=WorkflowStatus.COMPLETED)
        assert qs.count() == 1

    def test_get_executions_filter_by_document(self):
        org = OrganizationFactory()
        user = UserFactory(organization=org)
        doc = DocumentFactory(organization=org, created_by=user)
        WorkflowExecutionFactory(organization=org, document=doc)
        WorkflowExecutionFactory(organization=org)
        qs = get_executions(organization=org, document=doc)
        assert qs.count() == 1

    def test_get_executions_tenant_isolation(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        WorkflowExecutionFactory(organization=org_a)
        WorkflowExecutionFactory(organization=org_b)
        assert get_executions(organization=org_a).count() == 1

    def test_get_execution_by_id_other_org_not_found(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        execution = WorkflowExecutionFactory(organization=org_a)
        with pytest.raises(NotFound):
            get_execution_by_id(organization=org_b, execution_id=execution.id)
