from django.contrib.postgres.search import SearchVector
from django.db import migrations
from django.db.models import Value


def backfill_search_vector(apps, schema_editor):
    """
    Populate search_vector for documents created before the post_save signal
    was wired up. After this migration the signal keeps the field current.

    Tags are an ArrayField so they cannot be referenced as a plain column name
    inside SearchVector — they are fetched per row and passed as a Value().
    The other text columns (name, description, ocr_content) are read directly
    by PostgreSQL inside the UPDATE expression, so only 'id' and 'tags' are
    fetched into Python memory.
    """
    Document = apps.get_model("documents", "Document")

    for doc in Document.objects.only("id", "tags").iterator(chunk_size=200):
        tags_text = " ".join(doc.tags) if doc.tags else ""
        Document.objects.filter(pk=doc.pk).update(
            search_vector=(
                SearchVector("name", weight="A", config="simple")
                + SearchVector("description", weight="B", config="simple")
                + SearchVector(Value(tags_text), weight="C", config="simple")
                + SearchVector("ocr_content", weight="D", config="simple")
            )
        )


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0001_initial_documents"),
    ]

    operations = [
        migrations.RunPython(
            backfill_search_vector,
            # Reversing leaves search_vector populated — acceptable because
            # the signal will keep it current going forward regardless.
            reverse_code=migrations.RunPython.noop,
        ),
    ]
