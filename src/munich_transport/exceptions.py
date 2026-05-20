"""Package-specific exceptions."""


class MunichTransportError(Exception):
    """Base class for all package-specific errors."""


class TransportError(MunichTransportError):
    """Raised when a request cannot be completed."""


class ApiError(MunichTransportError):
    """Raised when MVG returns a non-successful response."""

    def __init__(self, status: int, message: str, *, body: str | None = None) -> None:
        super().__init__(f"MVG API returned HTTP {status}: {message}")
        self.status = status
        self.body = body


class ParseError(MunichTransportError):
    """Raised when an MVG response does not match the expected shape."""
