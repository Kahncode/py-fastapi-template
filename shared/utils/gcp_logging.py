import structlog
from structlog.types import EventDict


def format_gcloud_logs(_logger: structlog.BoundLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """Add Google Cloud Logging severity level to the log event dict."""

    try:
        # Docs: https://docs.cloud.google.com/logging/docs/structured-logging
        # Ensure message key (Cloud Logging prefers "message")
        if "event" in event_dict:
            event_dict["message"] = event_dict.pop("event")

        # Map level -> severity
        level = event_dict.pop("level", "").lower()
        severity_mapping = {
            "debug": "DEBUG",
            "info": "INFO",
            "warning": "WARNING",
            "error": "ERROR",
            "critical": "CRITICAL",
        }
        event_dict["severity"] = severity_mapping.get(level, "DEFAULT")

        # Rename and merge httpResponse into httpRequest to get the nicer display in GCP Logging UI
        if "http_request" in event_dict:
            event_dict["httpRequest"] = event_dict.pop("http_request")

            if "http_response" in event_dict:
                request_dict = event_dict["httpRequest"]
                request_dict |= event_dict.pop("http_response")
                request_dict["latency"] = f"{request_dict.pop('processing_time')/1000}s"
                request_dict["requestMethod"] = request_dict.pop("method")
                request_dict["requestUrl"] = request_dict.pop("url")
                request_dict["status"] = request_dict.pop("status_code")

                body = request_dict.get("body", None)
                if body:
                    request_dict["responseSize"] = str(len(body))

                headers_dict = request_dict["headers"]
                if "content-length" in headers_dict:
                    request_dict["requestSize"] = headers_dict["content-length"]
                if "user-agent" in headers_dict:
                    request_dict["userAgent"] = headers_dict["user-agent"]

    except (KeyError, TypeError, AttributeError):  # Keep logging in case of unexpected structure
        pass

    return event_dict
