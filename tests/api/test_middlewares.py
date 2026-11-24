import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator
from http import HTTPStatus

import pytest
from fastapi import BackgroundTasks, FastAPI, Request, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send
from structlog.testing import capture_logs

from shared.core.catch_exception_middleware import CatchExceptionMiddleware
from shared.core.logging import MAX_LOGGED_RESPONSE_BODY_BYTES, RequestIDLoggerMiddleware, get_request_id
from shared.core.request_context import RequestContextMiddleware, request_context


def build_app(*, log_full: bool = True) -> tuple[FastAPI, dict[str, list]]:  # noqa: C901
    """Build an app wired like api.main (innermost to outermost), with routes recording what they observe."""
    seen: dict[str, list] = {"background": [], "stream": [], "ws": []}
    app = FastAPI()
    app.add_middleware(CatchExceptionMiddleware)
    app.add_middleware(RequestIDLoggerMiddleware, log_full=log_full)
    app.add_middleware(RequestContextMiddleware)

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"body": await request.json(), "request_id": get_request_id()}

    @app.get("/sync")
    def sync_route() -> dict:
        # Runs in the threadpool: the context must be copied over
        return {"request_id": get_request_id()}

    @app.get("/ctx-is-request")
    async def ctx_is_request(request: Request) -> dict:
        ctx = request_context.get()
        return {"same_state": ctx.state is request.state or ctx.state._state is request.state._state}  # noqa: SLF001

    @app.get("/boom")
    async def boom() -> None:
        msg = "kaboom"
        raise RuntimeError(msg)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def gen() -> AsyncIterator[bytes]:
            for i in range(3):
                # request_context must still be set while the body is streamed
                seen["stream"].append(get_request_id())
                yield f"chunk{i}".encode()

        return StreamingResponse(gen())

    @app.get("/stream-then-fail")
    async def stream_then_fail() -> StreamingResponse:
        async def gen() -> AsyncIterator[bytes]:
            yield b"partial"
            msg = "late failure"
            raise RuntimeError(msg)

        return StreamingResponse(gen())

    @app.get("/big")
    async def big() -> dict:
        return {"data": "x" * (MAX_LOGGED_RESPONSE_BODY_BYTES + 1)}

    @app.get("/background")
    async def background(tasks: BackgroundTasks) -> dict:
        async def task() -> None:
            await asyncio.sleep(0)
            seen["background"].append(get_request_id())

        tasks.add_task(task)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        seen["ws"].append(request_context.get(None) is not None)
        await websocket.send_text("hi")
        await websocket.close()

    return app, seen


@pytest.fixture
def app_and_seen() -> tuple[FastAPI, dict[str, list]]:
    return build_app()


@pytest.fixture
def client(app_and_seen: tuple[FastAPI, dict[str, list]]) -> Iterator[TestClient]:
    with TestClient(app_and_seen[0], raise_server_exceptions=False) as c:
        yield c


def test_request_id_generated_and_returned(client: TestClient) -> None:
    response = client.post("/echo", json={"a": 1})
    assert response.status_code == HTTPStatus.OK
    request_id = response.headers["X-Request-ID"]
    assert request_id
    assert response.json() == {"body": {"a": 1}, "request_id": request_id}


def test_request_id_propagated(client: TestClient) -> None:
    response = client.post("/echo", json={}, headers={"X-Request-ID": "abc"})
    assert response.headers["X-Request-ID"] == "abc"
    assert response.json()["request_id"] == "abc"


def test_context_available_in_sync_route(client: TestClient) -> None:
    response = client.get("/sync", headers={"X-Request-ID": "sync-id"})
    assert response.json() == {"request_id": "sync-id"}


def test_context_shares_request_state(client: TestClient) -> None:
    assert client.get("/ctx-is-request").json() == {"same_state": True}


def test_context_reset_after_request(client: TestClient) -> None:
    client.get("/sync")
    assert request_context.get(None) is None
    assert get_request_id() is None


def test_concurrent_requests_do_not_leak_context(client: TestClient) -> None:
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    def call(i: int) -> str:
        return client.get("/sync", headers={"X-Request-ID": f"id-{i}"}).json()["request_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(40)))
    assert results == [f"id-{i}" for i in range(40)]


def test_streaming_response_is_complete_and_keeps_context(
    client: TestClient, app_and_seen: tuple[FastAPI, dict[str, list]]
) -> None:
    response = client.get("/stream", headers={"X-Request-ID": "stream-id"})
    assert response.text == "chunk0chunk1chunk2"
    assert response.headers["X-Request-ID"] == "stream-id"
    assert app_and_seen[1]["stream"] == ["stream-id"] * 3


def test_background_task_keeps_context(client: TestClient, app_and_seen: tuple[FastAPI, dict[str, list]]) -> None:
    client.get("/background", headers={"X-Request-ID": "bg-id"})
    assert app_and_seen[1]["background"] == ["bg-id"]


def test_websocket_has_context(client: TestClient, app_and_seen: tuple[FastAPI, dict[str, list]]) -> None:
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_text() == "hi"
    assert app_and_seen[1]["ws"] == [True]


def test_unhandled_exception_returns_500_json(client: TestClient) -> None:
    with capture_logs() as logs:
        response = client.get("/boom", headers={"X-Request-ID": "boom-id"})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "error" in response.json()
    # Error response still goes through the logging middleware
    assert response.headers["X-Request-ID"] == "boom-id"
    assert any(log["event"] == "Unhandled exception occurred" and log["request_id"] == "boom-id" for log in logs)
    sent = next(log for log in logs if log["event"] == "Response sent")
    assert sent["http_response"]["status_code"] == HTTPStatus.INTERNAL_SERVER_ERROR


def test_exception_after_response_started_is_reraised(app_and_seen: tuple[FastAPI, dict[str, list]]) -> None:
    with TestClient(app_and_seen[0], raise_server_exceptions=True) as c, pytest.raises(RuntimeError, match="late"):
        c.get("/stream-then-fail")


def test_request_and_response_logging(client: TestClient) -> None:
    with capture_logs() as logs:
        client.post("/echo", json={"a": 1}, headers={"Authorization": "secret", "X-Request-ID": "log-id"})
    received = next(log for log in logs if log["event"] == "Request received")
    sent = next(log for log in logs if log["event"] == "Response sent")
    assert received["request_id"] == sent["request_id"] == "log-id"
    assert received["http_request"]["body"] == {"a": 1}
    assert "authorization" not in received["http_request"]["headers"]
    assert json.loads(sent["http_response"]["body"]) == {"body": {"a": 1}, "request_id": "log-id"}
    assert sent["http_response"]["status_code"] == HTTPStatus.OK


def test_large_response_body_not_logged_but_delivered(client: TestClient) -> None:
    with capture_logs() as logs:
        response = client.get("/big")
    assert len(response.json()["data"]) == MAX_LOGGED_RESPONSE_BODY_BYTES + 1
    sent = next(log for log in logs if log["event"] == "Response sent")
    assert sent["http_response"]["body"] is None


def test_log_full_disabled_does_not_consume_body() -> None:
    app, _ = build_app(log_full=False)
    with TestClient(app) as c, capture_logs() as logs:
        response = c.post("/echo", json={"a": 2})
    assert response.json()["body"] == {"a": 2}
    received = next(log for log in logs if log["event"] == "Request received")
    assert "body" not in received["http_request"]


async def test_chunked_request_body_is_replayed() -> None:
    """Multi-chunk bodies must be reassembled for the logger and replayed intact to the app."""
    app, _ = build_app()
    messages = [
        {"type": "http.request", "body": b'{"a":', "more_body": True},
        {"type": "http.request", "body": b' "chunked"}', "more_body": False},
    ]
    sent: list[dict] = []

    async def receive() -> dict:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/echo",
        "raw_path": b"/echo",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("testserver", 80),
        "client": ("testclient", 1),
        "root_path": "",
    }
    await app(scope, receive_cast(receive), send_cast(send))
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    assert json.loads(body)["body"] == {"a": "chunked"}


def receive_cast(fn: Callable) -> Receive:
    return fn


def send_cast(fn: Callable) -> Send:
    return fn
