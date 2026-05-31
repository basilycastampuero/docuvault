import pytest
from django.db import IntegrityError, transaction

from apps.audit.models import AuditAction, AuditLog
from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.core.exceptions import ConflictError, PermissionDenied, ValidationError
from apps.documents.models import DocumentStatus
from apps.documents.services import document_service
from apps.documents.tests.factories import DocumentFactory
from apps.organizations.tests.factories import OrganizationFactory
from apps.workflows.models import WorkflowExecution, WorkflowStatus, WorkflowStepAction
from apps.workflows.services import workflow_service


def _two_step_template(org, user):
    """Template: step1 (supervisor, not final) → step2 (org_admin, final)."""
    return workflow_service.create_template(
        organization=org,
        user=user,
        name="Approval",
        steps=[
            {
                "name": "Review",
                "order": 1,
                "required_role": UserRole.SUPERVISOR,
                "is_final": False,
            },
            {
                "name": "Approve",
                "order": 2,
                "required_role": UserRole.ORG_ADMIN,
                "is_final": True,
            },
        ],
    )


@pytest.mark.django_db
class TestCreateTemplate:
    def test_creates_template_with_ordered_steps(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        steps = list(template.steps.all())
        assert len(steps) == 2
        assert [s.order for s in steps] == [1, 2]
        assert steps[1].is_final is True

    def test_rejects_no_steps(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        with pytest.raises(ValidationError):
            workflow_service.create_template(
                organization=org, user=admin, name="Empty", steps=[]
            )

    def test_rejects_no_final_step(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        with pytest.raises(ValidationError):
            workflow_service.create_template(
                organization=org,
                user=admin,
                name="NoFinal",
                steps=[
                    {
                        "name": "S1",
                        "order": 1,
                        "required_role": UserRole.SUPERVISOR,
                        "is_final": False,
                    }
                ],
            )

    def test_rejects_duplicate_orders(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        with pytest.raises(ValidationError):
            workflow_service.create_template(
                organization=org,
                user=admin,
                name="Dup",
                steps=[
                    {
                        "name": "S1",
                        "order": 1,
                        "required_role": UserRole.SUPERVISOR,
                        "is_final": False,
                    },
                    {
                        "name": "S2",
                        "order": 1,
                        "required_role": UserRole.ORG_ADMIN,
                        "is_final": True,
                    },
                ],
            )


@pytest.mark.django_db
class TestStartWorkflow:
    def test_happy_path(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)

        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        assert execution.status == WorkflowStatus.IN_PROGRESS
        assert execution.current_step.order == 1
        assert execution.started_at is not None
        document.refresh_from_db()
        assert document.status == DocumentStatus.UNDER_REVIEW

    def test_inactive_template_raises(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        template.is_active = False
        template.save(update_fields=["is_active"])
        document = DocumentFactory(organization=org, created_by=admin)

        with pytest.raises(ConflictError):
            workflow_service.start_workflow(
                organization=org, user=admin, document=document, template=template
            )

    def test_template_from_other_org_raises(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        admin_a = UserFactory(organization=org_a, role=UserRole.ORG_ADMIN)
        admin_b = UserFactory(organization=org_b, role=UserRole.ORG_ADMIN)
        template_b = _two_step_template(org_b, admin_b)
        document_a = DocumentFactory(organization=org_a, created_by=admin_a)

        with pytest.raises(PermissionDenied):
            workflow_service.start_workflow(
                organization=org_a,
                user=admin_a,
                document=document_a,
                template=template_b,
            )

    def test_existing_active_execution_raises(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        with pytest.raises(ConflictError):
            workflow_service.start_workflow(
                organization=org, user=admin, document=document, template=template
            )

    def test_document_from_other_org_raises(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        admin_a = UserFactory(organization=org_a, role=UserRole.ORG_ADMIN)
        admin_b = UserFactory(organization=org_b, role=UserRole.ORG_ADMIN)
        template_a = _two_step_template(org_a, admin_a)
        document_b = DocumentFactory(organization=org_b, created_by=admin_b)

        with pytest.raises(PermissionDenied):
            workflow_service.start_workflow(
                organization=org_a,
                user=admin_a,
                document=document_b,
                template=template_a,
            )

    def test_db_constraint_blocks_second_active_execution(self):
        """
        The partial unique constraint is the race-proof backstop: even when the
        service's .exists() guard is bypassed, the DB refuses a second active
        execution for the same document.
        """
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        first_step = template.steps.order_by("order").first()
        WorkflowExecution.objects.create(
            organization=org,
            template=template,
            document=document,
            current_step=first_step,
            status=WorkflowStatus.IN_PROGRESS,
            started_by=admin,
        )

        # Wrap in a savepoint so the IntegrityError only rolls back this insert,
        # leaving the test's outer transaction usable for teardown.
        with pytest.raises(IntegrityError), transaction.atomic():
            WorkflowExecution.objects.create(
                organization=org,
                template=template,
                document=document,
                current_step=first_step,
                status=WorkflowStatus.PENDING,
                started_by=admin,
            )


@pytest.mark.django_db
class TestTemplateManagement:
    def test_update_template_renames_and_toggles_active(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)

        template = workflow_service.update_template(
            organization=org,
            user=admin,
            template=template,
            name="Renamed",
            description="new desc",
            is_active=False,
        )
        template.refresh_from_db()
        assert template.name == "Renamed"
        assert template.description == "new desc"
        assert template.is_active is False

    def test_soft_delete_template(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)

        workflow_service.soft_delete_template(
            organization=org, user=admin, template=template
        )
        template.refresh_from_db()
        assert template.deleted_at is not None

    def test_soft_delete_template_with_active_execution_raises(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        with pytest.raises(ConflictError):
            workflow_service.soft_delete_template(
                organization=org, user=admin, template=template
            )

    def test_reject_workflow_wrapper(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        execution = workflow_service.reject_workflow(
            organization=org, user=supervisor, execution=execution, reason="no good"
        )
        assert execution.status == WorkflowStatus.REJECTED
        document.refresh_from_db()
        assert document.status == DocumentStatus.REJECTED


@pytest.mark.django_db
class TestAdvanceStep:
    def _started(self, org, admin):
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )
        return execution, document

    def test_approve_non_final_advances_to_next_step(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, document = self._started(org, admin)

        execution = workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        assert execution.status == WorkflowStatus.IN_PROGRESS
        assert execution.current_step.order == 2
        document.refresh_from_db()
        assert document.status == DocumentStatus.UNDER_REVIEW

    def test_approve_final_completes_and_approves_document(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, document = self._started(org, admin)

        # advance past step 1 (supervisor) then step 2 (org_admin, final)
        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )
        execution.refresh_from_db()
        execution = workflow_service.advance_step(
            organization=org,
            user=admin,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        assert execution.status == WorkflowStatus.COMPLETED
        assert execution.current_step is None
        assert execution.completed_at is not None
        document.refresh_from_db()
        assert document.status == DocumentStatus.APPROVED

    def test_reject_fails_workflow_and_rejects_document(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, document = self._started(org, admin)

        execution = workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.REJECTED,
            comment="missing data",
        )

        assert execution.status == WorkflowStatus.REJECTED
        document.refresh_from_db()
        assert document.status == DocumentStatus.REJECTED

    def test_wrong_role_raises_permission_denied(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        execution, _ = self._started(org, admin)

        with pytest.raises(PermissionDenied):
            workflow_service.advance_step(
                organization=org,
                user=editor,
                execution=execution,
                action=WorkflowStepAction.APPROVED,
            )

    def test_admin_can_override_step_role(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        execution, _ = self._started(org, admin)

        # admin acts on a supervisor-required step
        execution = workflow_service.advance_step(
            organization=org,
            user=admin,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )
        assert execution.current_step.order == 2

    def test_advance_completed_execution_raises(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, _ = self._started(org, admin)
        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.REJECTED,
        )
        execution.refresh_from_db()

        with pytest.raises(ConflictError):
            workflow_service.advance_step(
                organization=org,
                user=admin,
                execution=execution,
                action=WorkflowStepAction.APPROVED,
            )

    def test_comment_does_not_change_state(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, document = self._started(org, admin)

        execution = workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.COMMENTED,
            comment="looks good so far",
        )

        assert execution.status == WorkflowStatus.IN_PROGRESS
        assert execution.current_step.order == 1
        assert execution.step_logs.count() == 1

    def test_other_org_execution_raises(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        admin_a = UserFactory(organization=org_a, role=UserRole.ORG_ADMIN)
        admin_b = UserFactory(organization=org_b, role=UserRole.ORG_ADMIN)
        execution_a, _ = self._started(org_a, admin_a)

        with pytest.raises(PermissionDenied):
            workflow_service.advance_step(
                organization=org_b,
                user=admin_b,
                execution=execution_a,
                action=WorkflowStepAction.APPROVED,
            )


@pytest.mark.django_db
class TestCancelWorkflow:
    def test_cancel_returns_document_to_draft(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        execution = workflow_service.cancel_workflow(
            organization=org, user=admin, execution=execution
        )

        assert execution.status == WorkflowStatus.CANCELLED
        document.refresh_from_db()
        assert document.status == DocumentStatus.DRAFT

    def test_non_initiator_non_admin_cannot_cancel(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        editor = UserFactory(organization=org, role=UserRole.EDITOR)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)
        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )

        with pytest.raises(PermissionDenied):
            workflow_service.cancel_workflow(
                organization=org, user=editor, execution=execution
            )


@pytest.mark.django_db
class TestWorkflowIntegration:
    def test_document_reaches_approved_only_via_workflow(self):
        """Manual status change to approved must still be blocked (Phase 2 guard)."""
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        document = DocumentFactory(organization=org, created_by=admin)

        with pytest.raises(ConflictError):
            document_service.change_document_status(
                organization=org,
                user=admin,
                document=document,
                new_status=DocumentStatus.APPROVED,
            )

    def test_transitions_generate_audit_logs(self):
        org = OrganizationFactory()
        admin = UserFactory(organization=org, role=UserRole.ORG_ADMIN)
        supervisor = UserFactory(organization=org, role=UserRole.SUPERVISOR)
        template = _two_step_template(org, admin)
        document = DocumentFactory(organization=org, created_by=admin)

        execution = workflow_service.start_workflow(
            organization=org, user=admin, document=document, template=template
        )
        workflow_service.advance_step(
            organization=org,
            user=supervisor,
            execution=execution,
            action=WorkflowStepAction.APPROVED,
        )

        exec_logs = AuditLog.objects.filter(
            organization=org, entity_type="workflow_execution"
        )
        assert exec_logs.filter(action=AuditAction.CREATE).exists()
        assert exec_logs.filter(action=AuditAction.STATUS_CHANGE).exists()
