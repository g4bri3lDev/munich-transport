"""Package-specific exceptions."""

from __future__ import annotations

TRANSIENT_HTTP_STATUSES = frozenset({429, 502, 503, 504})


class MunichTransportError(Exception):
    """Base class for all package-specific errors."""


class TransportError(MunichTransportError):
    """Raised when a request cannot be completed."""


class ApiError(MunichTransportError):
    """Raised when MVG returns a non-successful response."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        body: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(f"MVG API returned HTTP {status}: {message}")
        self.status = status
        self.body = body
        self.retry_after = retry_after

    @property
    def transient(self) -> bool:
        """Whether callers should treat this as a temporary upstream failure."""

        return self.status in TRANSIENT_HTTP_STATUSES


class ParseError(MunichTransportError):
    """Raised when an MVG response does not match the expected shape."""
