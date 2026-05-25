import uuid

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Soft-delete all objects in the queryset."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently delete all objects in the queryset."""
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """Default manager — excludes soft-deleted objects from all querysets."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )


class AllObjectsManager(models.Manager):
    """Manager that returns all objects, including soft-deleted ones."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        """Mark this instance as deleted without removing it from the database."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self) -> None:
        """Undo a soft delete."""
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
