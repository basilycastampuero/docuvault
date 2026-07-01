from django.db import models

from apps.core.models import BaseModel


class DocumentVersion(BaseModel):
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    storage_path = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="document_versions",
    )
    change_description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "document_versions"
        ordering = ["-version_number"]
        indexes = [
            models.Index(
                fields=["document", "-version_number"],
                name="idx_doc_versions_doc_version",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_document_versions_doc_version_alive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document.name} v{self.version_number}"
