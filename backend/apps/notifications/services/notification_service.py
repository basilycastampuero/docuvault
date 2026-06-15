import logging
import smtplib
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import TransientError
from apps.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from apps.notifications.selectors import notification_selector

if TYPE_CHECKING:
    from apps.authentication.models import User
    from apps.organizations.models import Organization
    from apps.workflows.models import WorkflowExecution, WorkflowStep

logger = logging.getLogger(__name__)


def notify_step_assigned(
    organization: "Organization",
    execution: "WorkflowExecution",
    step: "WorkflowStep",
) -> None:
    """Create Notification records for each user with the step's required_role
    and schedule async sending via on_commit.
    Called from workflow_service after transitioning to a new step.
    """
    recipients = notification_selector.get_recipients_for_role(
        organization=organization,
        role=step.required_role,
    )
    for recipient in recipients:
        notification = Notification.objects.create(
            organization=organization,
            recipient=recipient,
            channel=NotificationChannel.EMAIL,
            subject=f"Paso asignado: {step.name}",
            body=_render_body(execution, step, recipient),
            status=NotificationStatus.PENDING,
            metadata={
                "execution_id": str(execution.id),
                "step_id": str(step.id),
            },
        )
        transaction.on_commit(lambda n_id=notification.id: _dispatch_send(str(n_id)))
    logger.info(
        "notify_step_assigned: step=%s org=%s recipients=%d",
        step.id,
        organization.id,
        recipients.count(),
    )


def _dispatch_send(notification_id: str) -> None:
    """Enqueue send_notification Celery task from on_commit context."""
    from apps.notifications.tasks.notification_tasks import send_notification

    send_notification.delay(notification_id)


def _send(notification: "Notification") -> None:
    """Send the notification email. Called from the Celery task.

    Concurrency safety: uses an atomic UPDATE claim so that two Celery workers
    processing the same notification_id in parallel (e.g. autoretry overlapping
    the original) cannot both send the email. The worker whose UPDATE returns
    rowcount=1 owns the send; rowcount=0 means another worker already claimed
    it.

    Semantics: at-least-once. A crash between the claim and `save(status=SENT)`
    leaves the row in SENT; a retry after an SMTP failure resets to FAILED so
    the next attempt can reclaim. If exactly-once delivery is required in the
    future, introduce a 'processing' status with a migration and a sweep task
    for stale rows.
    """
    # Atomic claim: flip PENDING or FAILED → SENT optimistically.
    # Filter includes FAILED so autoretries after an SMTP failure can resend.
    claimed_count = Notification.objects.filter(
        pk=notification.pk,
        status__in=[NotificationStatus.PENDING, NotificationStatus.FAILED],
    ).update(
        status=NotificationStatus.SENT,
        sent_at=timezone.now(),
    )
    if claimed_count == 0:
        logger.info(
            "_send: notification %s already claimed or sent; skipping",
            notification.pk,
        )
        return

    notification.refresh_from_db()
    try:
        send_mail(
            subject=notification.subject,
            message=notification.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.recipient.email],
            fail_silently=False,
        )
        logger.info(
            "Notification %s sent to %s", notification.pk, notification.recipient.email
        )
    except smtplib.SMTPException as exc:
        # Release the claim so an autoretry can resend.
        Notification.objects.filter(pk=notification.pk).update(
            status=NotificationStatus.FAILED,
            sent_at=None,
        )
        logger.warning(
            "Notification %s SMTP failure: %s — will retry", notification.pk, exc
        )
        raise TransientError(str(exc)) from exc
    except Exception as exc:
        Notification.objects.filter(pk=notification.pk).update(
            status=NotificationStatus.FAILED,
            sent_at=None,
        )
        logger.error("Notification %s permanent failure: %s", notification.pk, exc)
        raise


def _render_body(
    execution: "WorkflowExecution",
    step: "WorkflowStep",
    recipient: "User",
) -> str:
    """Build plain-text email body. No HTML template in this iteration."""
    return (
        f"Hola {recipient.email},\n\n"
        f"Se te ha asignado el paso '{step.name}' en el documento "
        f"'{execution.document.name}'.\n\n"
        f"Ejecución ID: {execution.id}\n"
    )
