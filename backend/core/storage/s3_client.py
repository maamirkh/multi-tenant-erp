"""Abstract storage client and concrete S3/MinIO implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from core.config.settings import Settings


class StorageClient(ABC):
    """Abstract interface for object storage operations."""

    @abstractmethod
    def upload(self, file: BinaryIO, key: str) -> str:
        """Upload a file-like object to storage and return its public URL."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object by key. Silently ignores non-existent keys."""

    @abstractmethod
    def get_url(self, key: str) -> str:
        """Return the public URL for the given storage key."""


class S3StorageClient(StorageClient):
    """S3/MinIO storage client backed by boto3.

    Works with AWS S3 and MinIO (via ``endpoint_url``).
    """

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.S3_BUCKET
        self._endpoint = settings.S3_ENDPOINT
        self._region = settings.S3_REGION

        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )

    def upload(self, file: BinaryIO, key: str) -> str:
        """Upload ``file`` to the configured bucket under ``key``.

        Returns the public URL of the uploaded object.
        """
        self._client.upload_fileobj(file, self._bucket, key)
        return self.get_url(key)

    def delete(self, key: str) -> None:
        """Delete object ``key`` from the bucket.

        Silently ignores ``NoSuchKey`` errors so callers need not check existence.
        """
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code not in ("NoSuchKey", "404"):
                raise

    def get_url(self, key: str) -> str:
        """Return the public URL for ``key`` in the configured bucket."""
        if self._endpoint:
            return f"{self._endpoint.rstrip('/')}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
