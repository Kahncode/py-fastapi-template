# Agentic-style refactor of the template

## Summary

The template targets current versions (FastAPI 0.165, Python 3.15) and its dependency set
is already current. This change refactors the code toward the explicit, statically
traceable patterns a current FastAPI codebase uses: direct imports on the router path,
typed service construction, honest type annotations, and no import-time surprises.
The YAML-configurable services system and its string-based `services[].type` resolution
stay — they are the template's deploy-time flexibility feature (see Decisions).
No guidance files (AGENTS.md, README changes) are included, per the requester's decision.
Tracking issue: Kahncode/py-fastapi-template#3.

Revision note (spec v2): v1 claimed five files contained syntax errors blocking
compilation. That was wrong. The `except A, B:` clauses are valid under PEP 758
(Python 3.14+ allows unparenthesized exception tuples when no `as` follows); the project
requires Python >=3.15, ruff/black target `py315`, and CI ran green on that exact code
(run 45443300804, Python 3.15.2, 14 passed / 1 skipped). The v1 finding came from
checking with Python 3.13. Nothing needs fixing there, and no new check is needed for it.

## Technical design

### 1. Except clauses: no change

The unparenthesized `except` tuples in `shared/core/logging.py:151`,
`shared/services/local_file_storage.py:31`, `shared/services/s3_file_storage.py:50,80,91`,
`shared/services/sql_db.py:199`, and `shared/utils/gcp_logging.py:47` are valid Python
3.14+ syntax (PEP 758) — none uses `as`. The existing gates already cover this: ruff and
black parse with the `py315` target and accept the files, and the pytest workflow
compiles and runs the suite on 3.15. Parenthesizing is optional style, not a fix; left
as-is.

### 2. Explicit router wiring (`api/main.py`)

Replace `include_router(app, "shared.core.system.router", "system")` with direct imports:

```python
from api.core.dev_routes import router as dev_router
from shared.core.system import router as system_router

app.include_router(system_router, prefix="/v1/system")
...
app.include_router(dev_router, prefix="/dev")
```

The local `include_router` helper and the string form are deleted. Routers are code-known
structure: no config file can change them, so resolving hard-coded strings through
`importlib` buys no deploy-time flexibility — it only hides the route graph from readers,
IDEs, and coding agents. This is the only place symbol resolution is removed.
`resolve_symbol` stays for the two deploy-time-varying config features (`log_processors`,
`services[].type`).

### 3. Typed service construction (`shared/services/base_service.py`)

The YAML service registry is unchanged: services are still declared in config with
`services[].type` strings, resolved per deployment, swapped without code edits.
What changes is only how the YAML dict becomes an instance. Today
`BaseService.__init__(**kwargs)` does `setattr` for every key, so an unknown or misspelled
key silently becomes an attribute and fails far from the config file, with no IDE or
agent-visible surface. Instead, each concrete service gets explicit, typed constructor
parameters, still fed from the same YAML dict:

```python
class S3FileStorageService(FileStorageService):
    def __init__(self, bucket_name: str, access_key: str, secret_key: str,
                 endpoint_url: str, root_path: Path = Path()) -> None: ...
```

`load_config_object`/`load_config_object_array` keep working unchanged; construction now
validates names and types in one typed place. Unknown YAML keys raise `TypeError` at
startup instead of being silently set. `LocalFileStorageService` gains `root_path: Path`
as a constructor parameter; `tests/conftest.py` passes it instead of assigning after
construction.

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

- **Keep the YAML service registry and `services[].type` symbol resolution.** The
  requester built this for fast service swapping across deployment contexts without
  rewriting code, and that benefit is real: local/S3/GCS/SFTP storage, Cloud SQL, and
  log processors are chosen per environment from config. v1's "full re-architecture"
  candidate (plain pydantic-settings + explicit DI) was listed as *rejected* on the
  issue and stays rejected. The refactor deliberately does not touch it.
- **De-indirect only the router path.** The router strings in `api/main.py` are constants
  in code, not config: they cannot vary per deployment, so the resolver there provides
  only indirection cost. Direct imports keep the same runtime behavior with a statically
  traceable graph.
- **Typed constructors, YAML-fed.** Configuration stays in YAML; only the unvalidated
  `setattr` spray is replaced. This keeps the registry's flexibility while giving every
  service an explicit, checkable config surface.
- **Fail fast (503) instead of yielding `None`.** Passing `None` into typed handlers was
  the most error-prone pattern in the dependency path. Alternative considered: keep
  `T | None` — rejected because every endpoint would need a None guard.
- **`async_sessionmaker` over legacy `sessionmaker`**: current SQLAlchemy 2.x API.
- **No parenthesization of except tuples**: valid PEP 758 syntax on the required runtime;
  ruff/black/CI already accept it.

## Assumptions

- The refactor stays behavior-preserving except the two intended changes: unknown YAML
  service keys now raise instead of silently setting attributes, and unconfigured
  services now 503 instead of yielding `None`.
- CI (`.github/workflows/pytest.yaml`, PostgreSQL-backed) is the source of truth for the
  integration tests; the sandbox runs only the DB-free subset.

## Out of scope

- No AGENTS.md / WARP.md / README or other guidance files (requester's explicit choice).
- No dependency version changes (already current as of 2026-11-24).
- No changes to the YAML config contract: `services[].type`, `log_processors`, and
  existing keys keep their meaning.
- No except-clause parenthesization migration.

## Validation criteria

Using the project's own Python via `uv` (provisions cpython-3.15.2; requires-python is
>=3.15, so 3.15 is the only compatibility target):

1. `uv run python -m compileall -q api shared tests` — exit 0.
2. `uv run ruff check api shared tests` — exit 0 (auto-fix config stays as-is).
3. `uv run black --check api shared tests` — exit 0.
4. `uv run pytest tests/api/test_middlewares.py tests/api/test_system.py` — pass (DB-free subset).
5. `CONFIG_YAML_PATH=tests/config.yaml uv run python -c "from api.main import app; print('ok')"` — app constructs.
6. Full `uv run pytest` in CI (pytest.yaml) — green, including PostgreSQL-backed tests.
