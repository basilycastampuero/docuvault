"""
Integration tests: workflow_service notification hooks.

Uses @pytest.mark.django_db(transaction=True) so that transaction.on_commit()
callbacks fire during the test. CELERY_TASK_ALWAYS_EAGER=True (test settings)
makes send_notification run synchronously inside on_commit, which hits
notification_service._send and populates mail.outbox via the locmem backend.
"""

import pytest
from django.core import mail

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.tests.factories import DocumentFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.workflows.models import WorkflowStepAction
from apps.workflows.services import workflow_service
from apps.workflows.tests.factories import WorkflowStepFactory, WorkflowTemplateFactory


def _build_two_step_template(org):
    """
    Create a template with two steps in the same org:
      step 1 — SUPERVISOR, non-final
      step 2 — ORG_ADMIN, final
    Steps are created with explicit order to avoid sequence collisions across tests.
    """
    template = WorkflowTemplateFactory(organization=org)
    step1 = WorkflowStepFactory(
        template=template,
        name="Review",
        order=1,
        required_role=UserRole.SUPERVISOR,
        is_final=False,
    )
    step2 = WorkflowStepFactory(
        template=template,
        name="Approve",
        order=2,
        required_role=UserRole.ORG_ADMIN,
        is_final=True,
    )
    return template, step1, step2


@pytest.mark.django_db(transaction=True)
class TestStartWorkflowNotifications:
    def test_start_workflow_enqueues_notification_to_first_step_role(self):
        """Should send an email to each supervisor after start_workflow commits."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template, step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        workflow_service.start_workflow(
            organization=org, user=admin, document=doc, template=template
        )

        assert len(mail.outbox) == 1
        assert supervisor.email in mail.outbox[0].to

    def test_start_workflow_no_notification_when_no_recipient_for_first_step(self):
        """Should send zero emails when no active user holds the first step role."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        # No supervisors in this org
        template, _step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        workflow_service.start_workflow(
            organization=org, user=admin, document=doc, template=template
        )

        assert len(mail.outbox) == 0


@pytest.mark.django_db(transaction=True)
class TestAdvanceStepNotifications:
    def test_approve_non_final_step_enqueues_notification_to_next_role(self):
        """Should send an email to org_admins after approving a non-final step."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template, _step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        # start_workflow will notify the supervisor (step 1); capture that separately
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=doc, template=template
        )
        mail.outbox.clear()  # reset — only care about the advance notification

        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        # After approving step 1, org_admin should be notified for step 2
        assert len(mail.outbox) == 1
        assert admin.email in mail.outbox[0].to

    def test_approve_final_step_sends_no_notification(self):
        """Should not send a notification when approving the final step (no next step)."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template, _step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=doc, template=template
        )
        mail.outbox.clear()

        # Advance through step 1 (non-final)
        execution = workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )
        mail.outbox.clear()  # reset again — only care about the final step

        # Advance through step 2 (final) — org_admin approves
        workflow_service.advance_step(
            organization=org,
            user=admin,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        assert len(mail.outbox) == 0

    def test_reject_step_sends_no_notification(self):
        """Should not send any notification when a step is rejected."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template, _step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=doc, template=template
        )
        mail.outbox.clear()

        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.REJECTED,
        )

        assert len(mail.outbox) == 0

    def test_multiple_admins_each_receive_email_on_step_advance(self):
        """Should send individual emails to all org_admins when advancing to step 2."""
        org = OrganizationFactory()
        admin1 = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        admin2 = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template, _step1, _step2 = _build_two_step_template(org)
        doc = DocumentFactory(organization=org)

        mail.outbox.clear()
        execution = workflow_service.start_workflow(
            organization=org, user=admin1, document=doc, template=template
        )
        mail.outbox.clear()

        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        sent_recipients = {addr for m in mail.outbox for addr in m.to}
        assert admin1.email in sent_recipients
        assert admin2.email in sent_recipients
        assert supervisor.email not in sent_recipients
