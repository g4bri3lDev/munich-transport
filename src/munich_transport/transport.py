"""HTTP transport abstraction and aiohttp implementation."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, cast

import aiohttp

from .exceptions import ApiError, TransportError
from .types import JsonValue


class Transport(Protocol):
    """Minimal async transport used by the client."""

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        """Return decoded JSON for a GET request."""


class AiohttpTransport:
    """aiohttp-backed transport for MVG's official browser endpoints."""

    def __init__(
        self,
        *,
        base_url: str = "https://www.mvg.de",
        session: aiohttp.ClientSession | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
        self._session = None

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        session = await self._ensure_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
        }
        try:
            async with session.get(url, params=params, headers=headers) as response:
                text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise ApiError(response.status, response.reason or "", body=text)
                try:
                    payload = await response.json(content_type=None)
                    return cast(JsonValue, payload)
                except aiohttp.ContentTypeError as error:
                    raise TransportError("Response did not contain JSON") from error
                except ValueError as error:
                    raise TransportError("Response contained invalid JSON") from error
        except TimeoutError as error:
            raise TransportError("Request timed out") from error
        except aiohttp.ClientError as error:
            raise TransportError(str(error)) from error

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session
