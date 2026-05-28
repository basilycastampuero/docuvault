from django.core.management.base import BaseCommand

from apps.documents.storage import StorageService


class Command(BaseCommand):
    help = "Ensure the MinIO/S3 bucket exists. Idempotent — safe to run multiple times."

    def handle(self, *args, **options) -> None:
        storage = StorageService()
        storage.ensure_bucket()
        self.stdout.write(self.style.SUCCESS("Storage bucket is ready."))
