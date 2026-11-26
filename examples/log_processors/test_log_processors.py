import json

import pytest
import structlog
from log_processors import REDACTED, redact_sensitive


def test_redact_sensitive_redacts_top_level_and_nested_keys() -> None:
    event = {
        "event": "login",
        "user": "alice",
        "password": "hunter2",
        "request": {"headers": {"authorization": "Bearer x"}, "token": "t"},
    }

    result = redact_sensitive(None, "info", event)

    assert result is event
    assert result["password"] == REDACTED
    assert result["request"]["headers"]["authorization"] == REDACTED
    assert result["request"]["token"] == REDACTED
    assert result["user"] == "alice"  # untouched


def test_processor_works_in_a_structlog_pipeline(capsys: pytest.CaptureFixture[str]) -> None:
    try:
        structlog.configure(
            processors=[redact_sensitive, structlog.processors.JSONRenderer()], cache_logger_on_first_use=False
        )
        structlog.get_logger().info("login attempt", user="alice", password="hunter2")
        rendered = json.loads(capsys.readouterr().out)
    finally:
        structlog.reset_defaults()

    assert rendered["event"] == "login attempt"
    assert rendered["password"] == REDACTED
    assert rendered["user"] == "alice"
