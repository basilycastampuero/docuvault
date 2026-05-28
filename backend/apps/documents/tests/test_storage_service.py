import io
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from apps.documents.storage.storage_service import StorageService


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": ""}}, "HeadBucket")


@pytest.fixture
def mock_boto3(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(
        "apps.documents.storage.storage_service.boto3.client",
        lambda *args, **kwargs: mock_client,
    )
    return mock_client


class TestStorageService:
    def test_upload_file_calls_put_object(self, mock_boto3):
        svc = StorageService()
        f = io.BytesIO(b"content")
        path = svc.upload_file(f, "org/file.pdf", "application/pdf")
        mock_boto3.put_object.assert_called_once_with(
            Bucket=svc._bucket,
            Key="org/file.pdf",
            Body=f,
            ContentType="application/pdf",
        )
        assert path == "org/file.pdf"

    def test_get_presigned_url_calls_generate(self, mock_boto3):
        mock_boto3.generate_presigned_url.return_value = "https://example.com/signed"
        svc = StorageService()
        url = svc.get_presigned_url("org/file.pdf", expires=600)
        mock_boto3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": svc._bucket, "Key": "org/file.pdf"},
            ExpiresIn=600,
        )
        assert url == "https://example.com/signed"

    def test_delete_file_calls_delete_object(self, mock_boto3):
        svc = StorageService()
        svc.delete_file("org/file.pdf")
        mock_boto3.delete_object.assert_called_once_with(
            Bucket=svc._bucket, Key="org/file.pdf"
        )

    def test_ensure_bucket_creates_when_missing(self, mock_boto3):
        mock_boto3.head_bucket.side_effect = _make_client_error("404")
        svc = StorageService()
        svc.ensure_bucket()
        mock_boto3.create_bucket.assert_called_once_with(Bucket=svc._bucket)

    def test_ensure_bucket_skips_create_when_exists(self, mock_boto3):
        mock_boto3.head_bucket.return_value = {}
        svc = StorageService()
        svc.ensure_bucket()
        mock_boto3.create_bucket.assert_not_called()

    def test_build_storage_path_format(self):
        path = StorageService.build_storage_path("org-1", "doc-42", "report.pdf")
        parts = path.split("/")
        assert parts[0] == "org-1"
        assert parts[3] == "doc-42"
        assert parts[4] == "report.pdf"
        assert len(parts) == 5
