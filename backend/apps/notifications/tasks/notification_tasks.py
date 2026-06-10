import logging

from celery import shared_task

from apps.core.exceptions import TransientError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def send_notification(self, notification_id: str) -> None:
    """Thin dispatcher → notification_service._send (CLAUDE.md §12).

    Idempotent: if the notification is already SENT, returns without error.
    Retries only on TransientError (SMTP transient failures). Permanent failures
    propagate and mark the task as failed without further retries.
    """
    from apps.notifications.models import Notification
    from apps.notifications.services import notification_service

    try:
        notification = Notification.objects.select_related("recipient").get(
            id=notification_id
        )
    except Notification.DoesNotExist:
        logger.warning("send_notification: %s not found; skipping", notification_id)
        return

    notification_service._send(notification)
