import io
import os
import time

import pytest
import yaml

import shared.services.s3_file_storage


@pytest.mark.skipif(not os.getenv("S3_FILE_STORAGE_TEST_CONFIG"), reason="Only run in CI or with relevant config")
async def test_s3_file_storage() -> None:
    yaml_config_str = os.getenv("S3_FILE_STORAGE_TEST_CONFIG")
    assert yaml_config_str, "S3_FILE_STORAGE_TEST_CONFIG environment variable not set"
    yaml_config = yaml.safe_load(yaml_config_str)
    s3 = shared.services.s3_file_storage.S3FileStorageService(**yaml_config)

    file_content = "This is a test file."
    file_stream = io.BytesIO(file_content.encode("utf-8"))

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.gmtime())
    test_filename = f"testfile_{timestamp}"

    success = await s3.upload_file_with_id(test_filename, file_stream.read(), "txt")
    assert success, "Failed to upload file to S3"

    file_exists = await s3.exists(s3.get_storage_path(test_filename, "txt"))
    assert file_exists, "Uploaded file does not exist in S3"
