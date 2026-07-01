import uuid
from unittest.mock import patch

import pytest

from apps.authentication.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationStatus
from apps.notifications.tasks.notification_tasks import send_notification
from apps.organizations.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestSendNotificationTask:
    def _make_pending_notification(self):
        """Helper: create a minimal PENDING Notification."""
        org = OrganizationFactory()
        recipient = UserFactory(organization=org)
        return Notification.objects.create(
            organization=org,
            recipient=recipient,
            subject="Task test subject",
            body="Task test body",
            status=NotificationStatus.PENDING,
            metadata={},
        )

    def test_task_delegates_to_notification_service_send(self):
        """Should call notification_service._send exactly once with the correct Notification."""
        notif = self._make_pending_notification()

        with patch(
            "apps.notifications.services.notification_service._send"
        ) as mock_send:
            send_notification(str(notif.id))

        mock_send.assert_called_once()
        called_notif = mock_send.call_args[0][0]
        assert called_notif.id == notif.id

    def test_task_noop_on_missing_notification(self):
        """Should return silently without error when the notification_id does not exist."""
        non_existent_id = str(uuid.uuid4())

        with patch(
            "apps.notifications.services.notification_service._send"
        ) as mock_send:
            # Must not raise
            send_notification(non_existent_id)

        mock_send.assert_not_called()
