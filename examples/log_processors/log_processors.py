"""
Custom structlog processor example, wired through `Settings.log_processors`.

`shared.core.logging` appends every callable in `Settings.log_processors` to its structlog processor chain.
Reference the processor by symbol in a config YAML, resolved by name at startup:

    log_processors:
      - "api.core.observability.redact_sensitive"

Note: the `examples/` folder is not packaged into the wheel or the Docker image, so move this function into
`api/` or `shared/` before referencing it from a deployed configuration.
"""

from structlog import BoundLogger
from structlog.types import EventDict

SENSITIVE_KEYS = frozenset({"password", "token", "authorization", "api_key", "secret"})
REDACTED = "***REDACTED***"


def _redact(data: dict) -> None:
    for key, value in list(data.items()):
        if str(key).lower() in SENSITIVE_KEYS:
            data[key] = REDACTED
        elif isinstance(value, dict):
            _redact(value)


def redact_sensitive(_logger: BoundLogger, _name: str, event_dict: EventDict) -> EventDict:
    """Replace the values of sensitive event keys with a placeholder, in place, including in nested dicts."""
    _redact(event_dict)
    return event_dict
