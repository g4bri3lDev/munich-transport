# Munich Transport

Async Python client for Munich public transport data.

This package is intentionally independent from Home Assistant. A Home Assistant
integration can later use it as a thin adapter.

## Endpoint Source

The endpoint shapes in this package are based on network traffic captured from
the official MVG website with Chrome DevTools MCP. External client
implementations and the legacy integration are not used as references.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy
```
