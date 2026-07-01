from django.db import models


class WorkflowStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"


class WorkflowStepAction(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    COMMENTED = "commented", "Commented"
