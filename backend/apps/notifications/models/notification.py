from django.db import models

from apps.core.models import BaseModel


class NotificationChannel(models.TextChoices):
    EMAIL = "email", "Email"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class Notification(BaseModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.EMAIL,
    )
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(
                fields=["organization", "recipient"],
                name="idx_notifs_org_recipient",
            ),
            models.Index(
                fields=["organization", "status"],
                name="idx_notifs_org_status",
            ),
        ]

    def __str__(self) -> str:
        return f"Notification({self.channel}) to {self.recipient_id} [{self.status}]"
