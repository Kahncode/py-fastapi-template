import hashlib
from abc import abstractmethod
from pathlib import Path

from shared.services.base_service import BaseService


class FileStorageService(BaseService):

    def compute_file_id(self, file: bytes) -> str:
        """Compute a unique file ID (MD5 hash) for the file content."""
        md5 = hashlib.md5()  # noqa: S324 # MD5 is acceptable for non-security use cases and is fast
        md5.update(file)
        return md5.hexdigest()

    def get_storage_path(self, file_id: str, extension: str | None) -> Path:
        """
        Generate a deterministic storage path for an file based on its hash.

        The path splits the first six characters of the hash into two directory
        levels (3 characters each) to distribute files evenly and avoid
        overloading any single folder. Each hex character has 16 possibilities,
        so 3 characters gives 16^3 = 4,096 folders per level. Two levels results
        in 4,096 * 4,096 ≈ 16.7 million possible folders.

        For example, if storing 100 million files:
            - Total possible folders: 16.7 million
            - Average files per folder: 100 000 000 / 16 777 216 ≈ 6 files
            - Average files per folder: 1 000 000 000 / 16 777 216 ≈ 60 files
            - Maximum files per folder will vary slightly depending on hash distribution,
            but will remain very small and manageable.

        Folder structure example for file_id 'abcdef123456...':
            abc/def/abcdef123456...
        """
        ext = ""
        if extension:
            ext = f".{extension.lstrip('.')}"
        return Path(f"{file_id[:3]}/{file_id[3:6]}/{file_id}{ext}")

    @abstractmethod
    def get_url(self, storage_path: Path) -> str:
        """Generate a URL which will identify the resource uniquely (including the details of the storage platform)."""
        ...

    @abstractmethod
    async def upload_file_with_id(self, file_id: str, file: bytes, extension: str | None) -> bool:
        """Save the file using the given file_id. Returns True if successful."""
        ...

    async def upload_file(self, file: bytes, extension: str | None) -> bool:
        """Save the file using the given file_id. Returns True if successful."""
        await self.upload_file_with_id(self.compute_file_id(file), file, extension)

    @abstractmethod
    async def exists(self, storage_path: Path) -> bool:
        """Check if a file exists at the given storage path. Returns True if it exists."""
        ...
