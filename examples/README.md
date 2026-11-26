# Examples

Self-contained example implementations built on this template's `shared/` library. They are reference code
to copy from, not part of the template runtime.

| Example | Demonstrates |
| --- | --- |
| [`crud_router/`](./crud_router/) | Typed CRUD router with pagination and filtering |
| [`background_tasks/`](./background_tasks/) | Background task wrapper that logs failures instead of losing them |
| [`jwt_oauth2/`](./jwt_oauth2/) | JWT issuing/validation over the OAuth2 password flow |
| [`log_processors/`](./log_processors/) | Custom structlog processor wired via `Settings.log_processors` |
| [`rate_limiting/`](./rate_limiting/) | Per-client IP rate limiting as a route dependency |

## Running the tests

```sh
uv run pytest examples/
```

## Removing the examples

Examples are excluded from the built wheel (`pyproject.toml` packages only `api` and `shared`) and from the
Docker image (`api/Dockerfile` copies only `./api/` and `./shared/`). To remove them entirely:

```sh
rm -rf examples/
uv remove --dev pyjwt  # only used by examples/jwt_oauth2/
```
