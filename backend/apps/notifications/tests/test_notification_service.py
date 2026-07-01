import smtplib
from unittest.mock import patch

import pytest
from django.core import mail

from apps.authentication.models import UserRole
from apps.authentication.tests.factories import UserFactory
from apps.documents.tests.factories import DocumentFactory
from apps.notifications.models import Notification, NotificationStatus
from apps.notifications.services import notification_service
from apps.organizations.tests.factories import OrganizationFactory
from apps.workflows.tests.factories import (
    WorkflowExecutionFactory,
    WorkflowStepFactory,
    WorkflowTemplateFactory,
)


def _make_execution_and_step(org, role=UserRole.SUPERVISOR):
    """Helper: build a template + step + execution all within the same org."""
    template = WorkflowTemplateFactory(organization=org)
    step = WorkflowStepFactory(template=template, required_role=role)
    doc = DocumentFactory(organization=org)
    execution = WorkflowExecutionFactory(
        organization=org,
        template=template,
        document=doc,
    )
    return execution, step


@pytest.mark.django_db
class TestNotifyStepAssigned:
    def test_creates_one_notification_per_recipient(self):
        """Should create one Notification record for every active user with the step role."""
        org = OrganizationFactory()
        supervisors = [
            UserFactory(organization=org, role=UserRole.SUPERVISOR) for _ in range(2)
        ]
        execution, step = _make_execution_and_step(org, role=UserRole.SUPERVISOR)

        notification_service.notify_step_assigned(
            organization=org, execution=execution, step=step
        )

        notifications = Notification.objects.filter(organization=org)
        assert notifications.count() == 2
        recipient_ids = set(notifications.values_list("recipient_id", flat=True))
        assert recipient_ids == {s.id for s in supervisors}

    def test_correct_subject_and_metadata(self):
        """Should embed step.name in subject and store execution_id / step_id in metadata."""
        org = OrganizationFactory()
        UserFactory(organization=org, role=UserRole.SUPERVISOR)
        execution, step = _make_execution_and_step(org, role=UserRole.SUPERVISOR)

        notification_service.notify_step_assigned(
            organization=org, execution=execution, step=step
        )

        notif = Notification.objects.get(organization=org)
        assert step.name in notif.subject
        assert notif.metadata["execution_id"] == str(execution.id)
        assert notif.metadata["step_id"] == str(step.id)

    def test_tenant_isolation_no_cross_org_notifications(self):
        """Should not create notifications for users belonging to a different org."""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        # Supervisors in org B — should never receive notifications for org A
        UserFactory(organization=org_b, role=UserRole.SUPERVISOR)
        UserFactory(organization=org_b, role=UserRole.SUPERVISOR)

        execution, step = _make_execution_and_step(org_a, role=UserRole.SUPERVISOR)

        notification_service.notify_step_assigned(
            organization=org_a, execution=execution, step=step
        )

        assert Notification.objects.filter(organization=org_a).count() == 0
        assert Notification.objects.filter(organization=org_b).count() == 0

    def test_no_notifications_when_no_recipients(self):
        """Should create zero Notification records when no user holds the step role."""
        org = OrganizationFactory()
        # Only viewers in the org — nobody is a supervisor
        UserFactory(organization=org, role=UserRole.VIEWER)
        execution, step = _make_execution_and_step(org, role=UserRole.SUPERVISOR)

        notification_service.notify_step_assigned(
            organization=org, execution=execution, step=step
        )

        assert Notification.objects.filter(organization=org).count() == 0


@pytest.mark.django_db
class TestSend:
    def _make_pending_notification(self, org=None, recipient=None):
        """Helper: create a PENDING notification ready for _send()."""
        if org is None:
            org = OrganizationFactory()
        if recipient is None:
            recipient = UserFactory(organization=org)
        execution, step = _make_execution_and_step(org)
        return Notification.objects.create(
            organization=org,
            recipient=recipient,
            subject="Test subject",
            body="Test body",
            status=NotificationStatus.PENDING,
            metadata={"execution_id": str(execution.id), "step_id": str(step.id)},
        )

    def test_send_updates_status_to_sent(self):
        """Should mark the notification SENT and set sent_at after a successful send."""
        org = OrganizationFactory()
        recipient = UserFactory(organization=org)
        notif = self._make_pending_notification(org=org, recipient=recipient)

        notification_service._send(notif)

        notif.refresh_from_db()
        assert notif.status == NotificationStatus.SENT
        assert notif.sent_at is not None
        assert len(mail.outbox) == 1
        assert recipient.email in mail.outbox[0].to

    def test_send_idempotent_for_already_sent_notification(self):
        """Should skip sending when the notification is already SENT (no duplicate email)."""
        org = OrganizationFactory()
        notif = self._make_pending_notification(org=org)
        # First send — marks it SENT
        notification_service._send(notif)
        assert len(mail.outbox) == 1

        # Second call — must not send another email
        notification_service._send(notif)

        assert len(mail.outbox) == 1  # still only one email

    def test_send_marks_failed_on_smtp_exception(self):
        """Should mark the notification FAILED and raise TransientError on SMTPException."""
        from apps.core.exceptions import TransientError

        org = OrganizationFactory()
        notif = self._make_pending_notification(org=org)

        with patch(
            "apps.notifications.services.notification_service.send_mail",
            side_effect=smtplib.SMTPException("Connection refused"),
        ):
            with pytest.raises(TransientError):
                notification_service._send(notif)

        notif.refresh_from_db()
        assert notif.status == NotificationStatus.FAILED
        assert len(mail.outbox) == 0

    def test_send_marks_failed_on_unexpected_exception(self):
        """Should mark the notification FAILED and re-raise non-SMTP exceptions."""
        org = OrganizationFactory()
        notif = self._make_pending_notification(org=org)

        with patch(
            "apps.notifications.services.notification_service.send_mail",
            side_effect=RuntimeError("Unexpected"),
        ):
            with pytest.raises(RuntimeError):
                notification_service._send(notif)

        notif.refresh_from_db()
        assert notif.status == NotificationStatus.FAILED

    def test_send_concurrent_claim_sends_once(self):
        """Simulates two workers with the same stale PENDING instance — only one email sent."""
        from django.test.utils import override_settings

        org = OrganizationFactory()
        recipient = UserFactory(organization=org)
        notif = self._make_pending_notification(org=org, recipient=recipient)

        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        ):
            mail.outbox = []
            # First worker wins the atomic claim and sends the email.
            notification_service._send(notif)
            assert len(mail.outbox) == 1

            # Second worker has a stale Python object with status=PENDING, but
            # the DB row is now SENT. The atomic UPDATE returns rowcount=0 → skip.
            notif_stale = Notification.objects.get(pk=notif.pk)
            # Manually set to PENDING in memory only (do NOT save) to simulate
            # a stale task that was enqueued before the first worker ran.
            notif_stale.status = NotificationStatus.PENDING
            notification_service._send(notif_stale)

            assert len(mail.outbox) == 1  # still only one email

    def test_send_failure_releases_claim_for_retry(self):
        """After SMTP failure the row returns to FAILED; the next attempt can resend."""
        from apps.core.exceptions import TransientError

        org = OrganizationFactory()
        recipient = UserFactory(organization=org)
        notif = self._make_pending_notification(org=org, recipient=recipient)

        # First attempt: SMTP fails → claim released back to FAILED.
        with patch(
            "apps.notifications.services.notification_service.send_mail",
            side_effect=smtplib.SMTPException("Timeout"),
        ):
            with pytest.raises(TransientError):
                notification_service._send(notif)

        notif.refresh_from_db()
        assert notif.status == NotificationStatus.FAILED
        assert len(mail.outbox) == 0

        # Second attempt: SMTP succeeds → claim is taken again, email sent.
        notification_service._send(notif)

        notif.refresh_from_db()
        assert notif.status == NotificationStatus.SENT
        assert len(mail.outbox) == 1
        assert recipient.email in mail.outbox[0].to
