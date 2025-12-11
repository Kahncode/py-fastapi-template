import mimetypes
from pathlib import Path

import aioboto3  # TODO: aioboto3 is heavy and contains all AWS SDK, try to find a better lightweight python package for this
import botocore.exceptions
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.core.logging import get_logger

from .file_storage import FileStorageService


class S3FileStorageService(FileStorageService):
    """
    S3FileStorageService provides an implementation of FileStorageService using Amazon S3 as the backend.

    Can be used with S3-compatible services such as Wasabi, DigitalOcean Spaces, MinIO, etc.
    """

    bucket_name: str = ""
    access_key: str = ""
    secret_key: str = ""
    endpoint_url: str = ""
    root_path: Path = Path()  # Assume root of the bucket if not set
    s3_session = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        if not self.bucket_name or not self.access_key or not self.secret_key or not self.endpoint_url:
            msg = "S3FileStorageService requires bucket_name, access_key, secret_key and endpoint_url to be set"
            raise ValueError(msg)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get_client(self) -> object:
        """
        Return an async S3 client using aioboto3, with retries and exponential backoff.
        """
        logger = get_logger()
        try:
            if not self.s3_session:
                self.s3_session = aioboto3.Session()
            s3_client = self.s3_session.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                endpoint_url=self.endpoint_url,
            )
            logger.debug("Successfully created S3 client", bucket=self.bucket_name)
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError):
            logger.exception("Failed to create S3 client", bucket=self.bucket_name)
            raise
        else:
            return s3_client

    def get_url(self, storage_path: Path) -> str:
        s3_path = str((self.root_path / storage_path).as_posix())
        return f"{self.endpoint_url}/{self.bucket_name}/{s3_path}"

    async def upload_file_with_id(self, file_id: str, file: bytes, extension: str | None) -> bool:
        """
        Save the file to S3 at the specified root path. Returns True if successful.
        """
        storage_path = self.get_storage_path(file_id, extension)
        s3_path = str((self.root_path / storage_path).as_posix())
        logger = get_logger()
        mime_type, _ = mimetypes.guess_type(str(storage_path))
        if mime_type is None:
            mime_type = "application/octet-stream"
        try:
            async with await self.get_client() as s3_client:
                response = await s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=s3_path, MaxKeys=1)
                exists = "Contents" in response and any(obj["Key"] == s3_path for obj in response["Contents"])
                if exists:
                    logger.error("File already exists", s3_path=s3_path)
                    return False
                await s3_client.put_object(Bucket=self.bucket_name, Key=s3_path, Body=file, ContentType=mime_type)
                logger.debug("Wrote S3 file", s3_path=s3_path)
                return True
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError):
            logger.exception("Error saving file to S3", s3_path=s3_path)
            return False

    async def exists(self, storage_path: Path) -> bool:
        """Check if a file exists at the given storage path. Returns True if it exists."""
        s3_path = str((self.root_path / storage_path).as_posix())
        try:
            async with await self.get_client() as s3_client:
                response = await s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=s3_path, MaxKeys=1)
                return "Contents" in response and any(obj["Key"] == s3_path for obj in response["Contents"])
        except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError):
            get_logger().exception("Failed list_objects_v2", bucket=self.bucket_name)
            return False
