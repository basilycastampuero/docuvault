from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.core.models import BaseModel


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ARCHIVED = "archived", "Archived"


class OcrStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class ThumbnailStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class Document(BaseModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    folder = models.ForeignKey(
        "documents.Folder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    mime_type = models.CharField(max_length=120)
    file_size = models.PositiveBigIntegerField()
    checksum = models.CharField(max_length=64)
    storage_path = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
    )
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        "authentication.User",
        on_delete=models.PROTECT,
        related_name="created_documents",
    )
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    ocr_content = models.TextField(blank=True)
    ocr_status = models.CharField(
        max_length=20,
        choices=OcrStatus.choices,
        default=OcrStatus.PENDING,
    )
    thumbnail_status = models.CharField(
        max_length=20,
        choices=ThumbnailStatus.choices,
        default=ThumbnailStatus.PENDING,
    )
    thumbnail_key = models.CharField(max_length=500, blank=True, default="")
    search_vector = SearchVectorField(null=True)

    class Meta:
        db_table = "documents"
        indexes = [
            models.Index(
                fields=["organization", "status"],
                name="idx_documents_org_status",
            ),
            models.Index(
                fields=["organization", "folder"],
                name="idx_documents_org_folder",
            ),
            models.Index(
                fields=["organization", "-created_at"],
                name="idx_documents_org_created",
            ),
            models.Index(
                fields=["organization", "checksum"],
                name="idx_documents_org_checksum",
            ),
            GinIndex(
                fields=["search_vector"],
                name="idx_documents_search_vector",
            ),
            GinIndex(
                fields=["metadata"],
                name="idx_documents_metadata_gin",
                opclasses=["jsonb_path_ops"],
            ),
            GinIndex(
                fields=["tags"],
                name="idx_documents_tags",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "folder", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="uq_documents_org_folder_name_alive",
            )
        ]

    def __str__(self) -> str:
        return self.name
