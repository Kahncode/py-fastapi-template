import mimetypes
from pathlib import Path

from google.cloud import storage
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.core.logging import get_logger

from .file_storage import FileStorageService


class GCSFileStorageService(FileStorageService):
    """
    GCSFileStorageService provides an implementation of FileStorageService using Google Cloud Storage (GCS) as the backend.

    Authentication:
    - For local development:
        - Install the Google Cloud CLI.
        - Run `gcloud auth application-default login` to authenticate with your user credentials.
    - For production or deployed environments:
        - Provide a Google Cloud service account with appropriate permissions.
        - Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to the path of the service account JSON credentials file.
        - Alternatively, use a more secure authentication system such as Workload Identity or Secret Manager, depending on your deployment environment.
    """

    bucket_name: str = ""
    project_id: str = ""
    root_path: Path = Path()  # Assume root of the bucket if not set
    gcs_client: storage.Client = None
    bucket: storage.Bucket = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        # Validate invariants
        if not self.bucket_name or not self.project_id:
            msg = "GCSFileStorageService requires bucket_name and project_id"
            raise ValueError(msg)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def ensure_connection(self) -> None:
        """
        Ensure the GCS client and bucket are initialized, with retries and exponential backoff.
        """
        logger = get_logger()
        try:
            if not self.gcs_client:
                self.gcs_client = storage.Client(project=self.project_id)
            if not self.bucket and self.bucket_name:
                self.bucket = self.gcs_client.bucket(self.bucket_name)
            logger.info("Successfully connected to GCS", bucket=self.bucket_name)
        except Exception:
            logger.exception("Failed to connect to GCS", bucket=self.bucket_name)
            raise

    def get_url(self, storage_path: Path) -> str:
        gcs_path = str((self.root_path / storage_path).as_posix())
        return f"gs://{self.bucket_name}/{gcs_path}"

    async def upload_file_with_id(self, file_id: str, file: bytes, extension: str | None) -> bool:
        """
        Save the file to GCS at the specified root path. Returns True if successful.
        """

        self.ensure_connection()

        storage_path = self.get_storage_path(file_id, extension)
        gcs_path = str((self.root_path / storage_path).as_posix())

        logger = get_logger()

        # Guess MIME type from file extension
        mime_type, _ = mimetypes.guess_type(str(storage_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        try:
            blob = self.bucket.blob(gcs_path)
            if blob.exists():
                logger.error("File already exists", gcs_path=gcs_path)
                return False
            blob.upload_from_string(file, content_type=mime_type)
        except Exception:
            logger.exception("Error saving file to GCS", gcs_path=gcs_path)
            return False
        else:
            logger.debug("Wrote GCS file", gcs_path=gcs_path)
            return True

    async def exists(self, storage_path: Path) -> bool:
        """Check if a file exists at the given storage path. Returns True if it exists."""
        self.ensure_connection()
        gcs_path = str((self.root_path / storage_path).as_posix())
        blob = self.bucket.blob(gcs_path)
        return blob.exists()
