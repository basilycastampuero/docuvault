from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "create", "Create"
    UPDATE = "update", "Update"
    DELETE = "delete", "Delete"
    RESTORE = "restore", "Restore"
    VIEW = "view", "View"
    DOWNLOAD = "download", "Download"
    STATUS_CHANGE = "status_change", "Status Change"
    LOGIN = "login", "Login"
    LOGOUT = "logout", "Logout"
    PERMISSION_DENIED = "permission_denied", "Permission Denied"


class AuditLog(models.Model):
    """Immutable append-only audit trail. Never update or delete rows."""

    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_index=True,
    )
    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    action = models.CharField(max_length=32, choices=AuditAction.choices)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "-created_at"],
                name="idx_audit_logs_org_created",
            ),
            models.Index(
                fields=["organization", "entity_type", "entity_id"],
                name="idx_audit_logs_org_entity",
            ),
            models.Index(
                fields=["organization", "user", "action"],
                name="idx_audit_logs_org_user_action",
            ),
        ]

    def __str__(self) -> str:
        return f"[{self.action}] {self.entity_type}:{self.entity_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("AuditLog entries are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("AuditLog entries are immutable and cannot be deleted.")
