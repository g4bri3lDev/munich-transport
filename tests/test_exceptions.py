from __future__ import annotations

from munich_transport.exceptions import ApiError


def test_api_error_marks_retryable_statuses_as_transient() -> None:
    assert ApiError(429, "rate limited").transient is True
    assert ApiError(502, "bad gateway").transient is True
    assert ApiError(503, "unavailable").transient is True
    assert ApiError(504, "gateway timeout").transient is True


def test_api_error_marks_non_retryable_statuses_as_not_transient() -> None:
    assert ApiError(400, "bad request").transient is False
    assert ApiError(401, "unauthorized").transient is False
    assert ApiError(404, "not found").transient is False
    assert ApiError(500, "server error").transient is False
