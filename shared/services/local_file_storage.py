from pathlib import Path

from shared.core.logging import get_logger

from .file_storage import FileStorageService


class LocalFileStorageService(FileStorageService):
    root_path: Path  # Do not assume a default SFTP path

    def get_url(self, storage_path: Path) -> str:
        """Return a file:// URL for the local file."""
        local_path = (self.root_path / storage_path).resolve()
        return f"file://{local_path.as_posix()}"

    async def upload_file_with_id(self, file_id: str, file: bytes, extension: str | None) -> bool:
        """Save the file to disk at the specified root path. Returns True if successful."""
        storage_path = self.get_storage_path(file_id, extension)
        local_path = self.root_path / storage_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger = get_logger()

        if local_path.exists():
            logger.error("File already exists", local_path=local_path)
            return False

        try:
            with local_path.open("wb") as f:
                f.write(file)
        except (OSError, ValueError):
            logger.exception("Error saving file", local_path=local_path)
            return False
        else:
            logger.debug("Wrote local file", local_path=local_path)
            return True

    async def exists(self, storage_path: Path) -> bool:
        """Check if a file exists at the given storage path. Returns True if it exists."""
        local_path = self.root_path / storage_path
        return local_path.exists()
