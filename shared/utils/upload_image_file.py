import asyncio
import base64
import io
from collections.abc import Awaitable, Callable
from typing import Annotated, Self

from fastapi import File, HTTPException, Request, UploadFile, status
from PIL import Image, UnidentifiedImageError

from shared.utils.size_utils import MEGABYTE, format_byte_size


# Custom UploadFile class which validates image files and checks constraints
class UploadImageFile(UploadFile):
    image: Image.Image | None = None
    _base64_cache: str | None = None
    _base64_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, file: UploadFile, previously_loaded: Self | None = None) -> None:
        super().__init__(file.file, filename=file.filename, size=file.size, headers=file.headers)
        if previously_loaded:
            self.image = previously_loaded.image

    async def validate_image(
        self,
        min_size: int | None = None,
        max_size: int | None = None,
        min_resolution: tuple[int, int] | None = None,
        max_resolution: tuple[int, int] | None = None,
    ) -> None:
        if not self.content_type or not self.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"error": "Unsupported Media Type", "content_type": self.content_type},
            )

        await self.load_image()

        self.validate_file_size(min_size, max_size)

        self.validate_image_resolution(min_resolution, max_resolution)

    async def load_image(self) -> None:
        if self.image:
            return  # Already loaded

        file_contents = await self.read()
        await self.seek(0)  # Reset file pointer to start

        try:
            self.image = Image.open(io.BytesIO(file_contents))  # move this before
        except (FileNotFoundError, UnidentifiedImageError, ValueError, TypeError) as err:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid image file"
            ) from err

    def validate_file_size(self, min_size: int | None = None, max_size: int | None = None) -> None:
        file_size = self.size

        if max_size and file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "error": "Image file too large",
                    "size": file_size,
                    "max_size": max_size,
                    "min_size": min_size,
                },
            )

        if min_size and file_size < min_size:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "error": "Image file too small",
                    "size": file_size,
                    "max_size": max_size,
                    "min_size": min_size,
                },
            )

    def validate_image_resolution(
        self,
        min_resolution: tuple[int, int] | None = None,
        max_resolution: tuple[int, int] | None = None,
    ) -> None:
        width, height = self.image.size
        if min_resolution:
            min_width, min_height = min_resolution
            if width < min_width or height < min_height:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={
                        "error": "Image resolution too small",
                        "resolution": (width, height),
                        "min_resolution": min_resolution,
                        "max_resolution": max_resolution,
                    },
                )
        if max_resolution:
            max_width, max_height = max_resolution
            if width > max_width or height > max_height:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail={
                        "error": "Image resolution too large",
                        "resolution": (width, height),
                        "min_resolution": min_resolution,
                        "max_resolution": max_resolution,
                    },
                )

    async def to_base64(self) -> str:
        """
        Convert original uploaded file to base64, cache result, coroutine-safe.

        The cache means that any further modification to the image will not be reflected in the base64 output.
        """
        if self._base64_cache is not None:
            return self._base64_cache
        async with self._base64_lock:
            await self.seek(0)
            file_bytes = await self.read()
            await self.seek(0)
            self._base64_cache = base64.b64encode(file_bytes).decode("utf-8")
            return self._base64_cache


def get_image_file(
    min_size: int | None = None,
    max_size: int | None = 5 * MEGABYTE,  # default max size 5MB for safety
    min_resolution: tuple[int, int] | None = (224, 224),  # default min resolution 224x224
    max_resolution: tuple[int, int] | None = None,
) -> Callable[[UploadFile], Awaitable[UploadImageFile]]:

    # Build description dynamically based on specified limits
    desc_parts = ["Image file to upload."]

    if min_size is not None:
        desc_parts.append(f"Minimum size: {format_byte_size(min_size)}.")
    if max_size is not None:
        desc_parts.append(f"Maximum size: {format_byte_size(max_size)}.")
    if min_resolution is not None:
        desc_parts.append(f"Minimum resolution: {min_resolution[0]}x{min_resolution[1]}.")
    if max_resolution is not None:
        desc_parts.append(f"Maximum resolution: {max_resolution[0]}x{max_resolution[1]}.")
    desc_parts.append("Supported formats: JPEG, PNG, BMP, GIF, TIFF, PPM, PGM, PBM, WebP.")

    description = " ".join(desc_parts)

    async def _get_image_file(
        image: Annotated[UploadFile, File(..., description=description)], request: Request
    ) -> UploadImageFile:

        # We cache already loaded files per filename to prevent loading the same image twice
        if not hasattr(request.state, "upload_image_file_cache"):
            request.state.upload_image_file_cache = {}
        image_cache: dict = request.state.upload_image_file_cache

        already_loaded: UploadImageFile | None = image_cache.get(image.filename)

        image_file = UploadImageFile(image, already_loaded)
        await image_file.validate_image(
            min_size=min_size,
            max_size=max_size,
            min_resolution=min_resolution,
            max_resolution=max_resolution,
        )

        # Cache it for this request by filename
        image_cache[image.filename] = image_file
        return image_file

    return _get_image_file
