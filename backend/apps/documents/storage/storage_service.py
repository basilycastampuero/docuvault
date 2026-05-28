import logging
from datetime import UTC, datetime
from typing import IO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            verify=settings.AWS_S3_VERIFY,
        )
        self._bucket = settings.AWS_STORAGE_BUCKET_NAME

    def ensure_bucket(self) -> None:
        """Create the bucket if it does not exist. Idempotent."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
            logger.debug("Bucket %s already exists.", self._bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
                logger.info("Bucket %s created.", self._bucket)
            else:
                raise

    def upload_file(self, file: IO[bytes], path: str, content_type: str) -> str:
        """Upload a file-like object and return the storage path."""
        self._client.put_object(
            Bucket=self._bucket,
            Key=path,
            Body=file,
            ContentType=content_type,
        )
        logger.debug("Uploaded %s to bucket %s", path, self._bucket)
        return path

    def get_presigned_url(self, path: str, expires: int = 3600) -> str:
        """Return a presigned URL valid for `expires` seconds."""
        url: str = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": path},
            ExpiresIn=expires,
        )
        return url

    def delete_file(self, path: str) -> None:
        """Remove a file from storage. No-op if the key does not exist."""
        self._client.delete_object(Bucket=self._bucket, Key=path)
        logger.debug("Deleted %s from bucket %s", path, self._bucket)

    @staticmethod
    def build_storage_path(org_id: str, document_id: str, filename: str) -> str:
        """Return a deterministic storage path: {org_id}/{YYYY}/{MM}/{doc_id}/{filename}."""
        now = datetime.now(UTC)
        return f"{org_id}/{now.year}/{now.month:02d}/{document_id}/{filename}"
