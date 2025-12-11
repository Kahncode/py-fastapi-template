from pathlib import Path

import paramiko
from tenacity import retry, stop_after_attempt, wait_exponential

from shared.core.logging import get_logger

from .file_storage import FileStorageService


class SFTPFileStorageService(FileStorageService):
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    root_path: Path  # Do not assume a default SFTP path
    sftp_client = None

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)

        # Validate invariants
        if not self.host or not self.username or not self.password or not self.port or not self.root_path:
            msg = "SFTPFileStorageService requires host, port, username, password, and root_path"
            raise ValueError(msg)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=10))
    def ensure_connection(self) -> None:
        """
        Ensure the SFTP client is connected. Reconnect if needed, with retries and exponential backoff.
        """
        logger = get_logger()
        if not self._is_connected():
            try:
                transport = paramiko.Transport((self.host, self.port))
                transport.connect(username=self.username, password=self.password)
                self.sftp_client = paramiko.SFTPClient.from_transport(transport)
                logger.info("Successfully connected to SFTP server", host=self.host, port=self.port)
            except Exception:
                logger.exception("Failed to connect to SFTP server", host=self.host, port=self.port)
                raise

    def _is_connected(self) -> bool:
        """
        Check if the SFTP client is connected.
        """
        try:
            if self.sftp_client is None:
                return False
            # Try a simple operation to check connection
            self.sftp_client.listdir(".")
        except paramiko.SSHException:
            return False
        else:
            return True

    def get_url(self, storage_path: Path) -> str:
        """Return an sftp:// URL for the remote file, including credentials and path."""
        remote_path = str((self.root_path / storage_path).as_posix())
        return f"sftp://{self.host}:{self.port}/{remote_path}"

    async def upload_file_with_id(self, file_id: str, file: bytes, extension: str | None) -> bool:
        """
        Save the file to SFTP at the specified root path. Returns True if successful.
        """
        self.ensure_connection()
        storage_path = self.get_storage_path(file_id, extension)
        remote_path = str((self.root_path / storage_path).as_posix())

        logger = get_logger()

        if self.exists(storage_path):
            logger.error("File already exists", remote_path=remote_path)
            return False

            # Ensure remote directories exist
        dirs = remote_path.rsplit("/", 1)[0]
        try:
            parts = dirs.split("/")
            current = ""
            for part in parts:
                current = f"{current}/{part}" if current else part
                try:
                    self.sftp_client.stat(current)
                except FileNotFoundError:
                    self.sftp_client.mkdir(current)
        except Exception:
            logger.exception("Error creating remote directories", remote_path=dirs)
            return False

        try:
            with self.sftp_client.open(remote_path, "wb") as remote_file:
                remote_file.write(file)
        except Exception:
            logger.exception("Error saving file to SFTP", remote_path=remote_path)
            return False
        else:
            logger.debug("Wrote SFTP file", remote_path=remote_path)
            return True

    async def exists(self, storage_path: Path) -> bool:
        """Check if a file exists at the given storage path. Returns True if it exists."""
        self.ensure_connection()
        remote_path = str((self.root_path / storage_path).as_posix())
        try:
            self.sftp_client.stat(remote_path)
        except FileNotFoundError:
            return False
        else:
            return True
