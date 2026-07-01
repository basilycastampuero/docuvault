from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.documents.models import Document

# Fields whose content feeds search_vector. A save that touches none of them
# (e.g. a status change, a version bump, a storage_path update) cannot affect
# the vector, so we skip the rebuild to avoid write amplification.
_SEARCHABLE_FIELDS = {"name", "description", "tags", "ocr_content"}


@receiver(post_save, sender=Document)
def update_search_vector(sender, instance: Document, **kwargs) -> None:
    """Rebuild search_vector when a searchable text field may have changed."""
    # queryset.update() is used below, which does NOT trigger post_save again,
    # so there is no recursion risk.
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and not (_SEARCHABLE_FIELDS & set(update_fields)):
        # A partial save that touched no searchable field: nothing to rebuild.
        return

    tags_text = " ".join(instance.tags) if instance.tags else ""

    vector = (
        SearchVector("name", weight="A", config="simple")
        + SearchVector("description", weight="B", config="simple")
        + SearchVector(Value(tags_text), weight="C", config="simple")
        + SearchVector("ocr_content", weight="D", config="simple")
    )
    Document.objects.filter(pk=instance.pk).update(search_vector=vector)
