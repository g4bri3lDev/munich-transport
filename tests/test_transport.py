from __future__ import annotations

import pytest

from munich_transport.exceptions import ApiError
from munich_transport.transport import AiohttpTransport


class FakeResponse:
    def __init__(self, status: int, payload: object, reason: str = "OK") -> None:
        self.status = status
        self.reason = reason
        self._payload = payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def text(self) -> str:
        return "body"

    async def json(self, *, content_type: str | None = None) -> object:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
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
        return self.response

    async def close(self) -> None:
        self.closed = True


async def test_aiohttp_transport_returns_json() -> None:
    session = FakeSession(FakeResponse(200, [{"ok": True}]))
    transport = AiohttpTransport(base_url="https://example.test", session=session)  # type: ignore[arg-type]

    result = await transport.get_json("/path", params={"a": "b"})

    assert result == [{"ok": True}]
    assert session.calls[0][0] == "https://example.test/path"
    assert session.calls[0][1] == {"a": "b"}


async def test_aiohttp_transport_raises_api_error_for_non_success() -> None:
    session = FakeSession(FakeResponse(503, {"error": True}, reason="Unavailable"))
    transport = AiohttpTransport(base_url="https://example.test", session=session)  # type: ignore[arg-type]

    with pytest.raises(ApiError) as error:
        await transport.get_json("/path")

    assert error.value.status == 503
