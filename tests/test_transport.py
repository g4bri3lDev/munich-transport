from __future__ import annotations

import aiohttp
import pytest

from munich_transport.exceptions import ApiError, TransportError
from munich_transport.transport import AiohttpTransport


class FakeResponse:
    def __init__(
        self,
        status: int,
        payload: object,
        reason: str = "OK",
        json_error: Exception | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self._payload = payload
        self._json_error = json_error

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def text(self) -> str:
        return "body"

    async def json(self, *, content_type: str | None = None) -> object:
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict[str, str] | None, dict[str, str]]] = []
        self.closed = False

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str],
    ) -> FakeResponse:
        self.calls.append((url, params, headers))
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response

    async def close(self) -> None:
        self.closed = True


async def test_aiohttp_transport_returns_json() -> None:
    session = FakeSession(FakeResponse(200, [{"ok": True}]))
    transport = AiohttpTransport(
        base_url="https://example.test",
        session=session,  # type: ignore[arg-type]
    )

    result = await transport.get_json("/path", params={"a": "b"})

    assert result == [{"ok": True}]
    assert session.calls[0][0] == "https://example.test/path"
    assert session.calls[0][1] == {"a": "b"}


async def test_aiohttp_transport_raises_api_error_for_non_success() -> None:
    session = FakeSession(FakeResponse(503, {"error": True}, reason="Unavailable"))
    transport = AiohttpTransport(
        base_url="https://example.test",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(ApiError) as error:
        await transport.get_json("/path")

    assert error.value.status == 503


async def test_aiohttp_transport_raises_transport_error_for_invalid_json() -> None:
    session = FakeSession(FakeResponse(200, None, json_error=ValueError("bad json")))
    transport = AiohttpTransport(
        base_url="https://example.test",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(TransportError, match="invalid JSON"):
        await transport.get_json("/path")


async def test_aiohttp_transport_raises_transport_error_for_timeout() -> None:
    session = FakeSession(error=TimeoutError())
    transport = AiohttpTransport(
        base_url="https://example.test",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(TransportError, match="timed out"):
        await transport.get_json("/path")


async def test_aiohttp_transport_raises_transport_error_for_client_error() -> None:
    session = FakeSession(error=aiohttp.ClientError("connection failed"))
    transport = AiohttpTransport(
        base_url="https://example.test",
        session=session,  # type: ignore[arg-type]
    )

    with pytest.raises(TransportError, match="connection failed"):
        await transport.get_json("/path")


async def test_aiohttp_transport_closes_owned_session_only() -> None:
    injected_session = FakeSession(FakeResponse(200, {}))
    injected_transport = AiohttpTransport(
        session=injected_session,  # type: ignore[arg-type]
    )

    await injected_transport.close()

    assert injected_session.closed is False
