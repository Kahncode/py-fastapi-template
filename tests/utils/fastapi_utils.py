import io
import os
import random
from unittest.mock import Mock

from fastapi import UploadFile
from PIL import Image

from shared.utils.upload_image_file import UploadImageFile
from tests.utils.random_utils import create_random_dict


def create_mock_request() -> Mock:
    """
    Provide a mock Request instance with a predefined URL path.
    """
    mock = Mock()
    mock.url.path = f"/test/route/{random.randint(1, 1000)}"  # noqa: S311
    mock.query_params = create_random_dict()
    mock._body = create_random_dict()  # noqa: SLF001
    mock.headers = {"User-Agent": "pytest-mock"}
    mock.method = random.choice(["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])  # noqa: S311

    async def _body() -> dict:
        return mock._body  # noqa: SLF001

    async def _json() -> dict:
        return mock._body  # noqa: SLF001

    mock.body = _body
    mock.json = _json

    return mock


def create_upload_file(size: int = 100) -> UploadFile:
    """
    Create a fake UploadFile with random bytes of the specified size.

    Not a fixture as we want to keep it parametrized
    """

    file_content = os.urandom(size)
    file_like = io.BytesIO(file_content)
    return UploadFile(
        filename="test.bin",
        file=file_like,
        size=len(file_like.getvalue()),
        headers={"content-type": "application/octet-stream"},
    )


def create_upload_image_file(size: tuple[int, int] = (100, 100)) -> UploadImageFile:
    """
    Create a fake UploadImageFile with an image of the specified size.

    Not a fixture as we want to keep it parametrized
    """
    img_format = "PNG"
    img = Image.new("RGB", size)
    buf = io.BytesIO()
    img.save(buf, format=img_format)
    buf.seek(0)
    return UploadImageFile(
        UploadFile(filename="test.png", file=buf, size=len(buf.getvalue()), headers={"content-type": "image/png"})
    )
