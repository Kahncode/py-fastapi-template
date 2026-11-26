# Agentic-style refactor of the template

## Summary

The template targets current versions (FastAPI 0.165, Python 3.15) but its code predates
agentic-coding workflows and currently does not compile: five files contain invalid
Python 2-style `except A, B, C:` clauses. This change fixes that blocker and refactors
the code toward the explicit, statically traceable patterns a current FastAPI codebase
uses: direct imports instead of string-based symbol resolution on the router path,
honest type annotations, typed service construction, and no import-time surprises.
No guidance files (AGENTS.md, README changes) are included, per the requester's decision.
Tracking issue: Kahncode/py-fastapi-template#3.

## Technical design

### 1. Fix the invalid except clauses (blocker)

Parenthesize every multi-exception clause so the package imports at all:

- `shared/core/logging.py:151` — `except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError):`
- `shared/services/local_file_storage.py:31` — `except (OSError, ValueError):`
- `shared/services/s3_file_storage.py:50`, `:80`, `:91` — parenthesize `BotoCoreError, ClientError`
- `shared/services/sql_db.py:199` — `except (ArgumentError, OperationalError, DBAPIError):`
- `shared/utils/gcp_logging.py:47` — `except (KeyError, TypeError, AttributeError):`

### 2. Explicit router wiring (`api/main.py`)

Replace `include_router(app, "shared.core.system.router", "system")` with direct imports:

```python
from api.core.dev_routes import router as dev_router
from shared.core.system import router as system_router

app.include_router(system_router, prefix="/v1/system")
...
app.include_router(dev_router, prefix="/dev")
```

The local `include_router` helper and the string form are deleted. Routers are
code-known structure; resolving them through `importlib` hides the graph from readers,
IDEs, and coding agents. `resolve_symbol` stays in `shared/core/config.py` for the two
deploy-time-varying config features (`log_processors`, `services[].type`).

### 3. Typed service construction (`shared/services/base_service.py`)

`BaseService.__init__(**kwargs)` currently `setattr`s arbitrary keys onto `self`.
Give `BaseService` an explicit no-arg `__init__` (pass) and give each concrete service
explicit, typed constructor parameters:

```python
class S3FileStorageService(FileStorageService):
    def __init__(self, bucket_name: str, access_key: str, secret_key: str,
                 endpoint_url: str, root_path: Path = Path()) -> None: ...
```

`load_config_object`/`load_config_object_array` keep working unchanged: YAML still
supplies the dict, but construction now validates names and types at one typed place
instead of spraying attributes. Unknown YAML keys raise `TypeError` instead of being
silently set. `LocalFileStorageService` gains `root_path: Path` as a constructor
parameter; `tests/conftest.py` passes it instead of assigning after construction.

### 4. Honest annotations and fail-fast service dependency

- `shared/services/sql_db.py`: `engine: AsyncEngine | None`, `session_maker` becomes
  `async_sessionmaker[AsyncSession] | None` (modern SQLAlchemy 2.0 API), and
  `get_session() -> AsyncSession | None` (it returns the context default `None`).
- `shared/services/service.py`: `get_service` stops yielding `None` into endpoints.
  When no service of that type is configured it raises `HTTPException(503)`. Endpoints
  can then declare `-> SQLDatabaseService`, not `-> SQLDatabaseService | None`.
- `shared/core/logging.py`: `get_logger(request: Request | None = None)` and
  `get_request_id(request: Request | None = None)`.

### 5. Remove import-time side effects and dead code

- `api/core/dev_routes.py`: drop the module-level `RuntimeError`. Dev routes are
  already gated by `is_dev_environment()` at both inclusion sites (`api/main.py`,
  `shared/core/system.py`); importing the module must be safe.
- `shared/core/config.py`: move `load_dotenv()` from import time into `get_settings()`,
  and replace the `print(...)` (avoided-circular-import workaround) with
  `logging.getLogger(__name__)`, which does not import `shared.core.logging`.
- `api/core/auth.py`: collapse `api_key_valid`/`authorized` (the second is derived from
  the first; the 403 branch is unreachable) to the single 401 check.

## Decisions

- Keep the YAML service registry; do not replace it with static DI. The registry is the
  template's deploy-time feature (local/S3/GCS/SFTP, Cloud SQL chosen per environment).
  Static wiring would force code edits per deployment. We only removed indirection where
  the structure is code-known (routers).
- Fail fast (503) instead of yielding `None`. Passing `None` into typed handlers was the
  most error-prone pattern in the dependency path. Alternative considered: keep
  `T | None` — rejected because every endpoint would need a None guard.
- `async_sessionmaker` over legacy `sessionmaker`: current SQLAlchemy 2.x API.

## Assumptions

- The refactor stays behavior-preserving except the two intended changes: unknown YAML
  service keys now raise instead of silently setting attributes, and unconfigured
  services now 503 instead of yielding `None`.
- CI (`.github/workflows/pytest.yaml`, PostgreSQL-backed) is the source of truth for the
  integration tests; the sandbox runs only the DB-free subset.

## Out of scope

- No AGENTS.md / WARP.md / README or other guidance files (requester's explicit choice).
- No dependency version changes (already current as of 2026-11-24).
- No new features, no CI workflow changes, no migration of `services[].type` config keys.

## Validation criteria

On Python 3.15 via `uv` (0.13.7 can provision cpython-3.15.2), from the repo root:

1. `uv run python -m compileall -q api shared tests` — exit 0.
2. `uv run ruff check api shared tests` — exit 0 (auto-fix config stays as-is).
3. `uv run black --check api shared tests` — exit 0.
4. `uv run pytest tests/api/test_middlewares.py tests/api/test_system.py` — pass (DB-free subset).
5. `CONFIG_YAML_PATH=tests/config.yaml uv run python -c "from api.main import app; print('ok')"` — app constructs.
6. Full `uv run pytest` in CI (pytest.yaml) — green, including PostgreSQL-backed tests.
