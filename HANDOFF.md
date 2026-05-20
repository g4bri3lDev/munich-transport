# Codex Handoff: Rewrite Munich Public Transport Python Client + Home Assistant Integration

## Context

I want to rewrite an old Munich public transport Home Assistant integration. The existing integration is ancient and contains many bad practices. Treat the old code only as a reference implementation, not as something to refactor in place.

I have several Python/software design books as PDFs in this repository/directory. Use them only as local reference material for concepts and design guidance. Do not copy large passages from them. The relevant themes are:

- Fluent Python: idiomatic Python, data model, dataclasses, protocols, async, context managers, typing
- Effective Python: pragmatic Python best practices
- Architecture Patterns with Python / Cosmic Python: clean boundaries, domain models, dependency inversion, testability
- Clean code / testing books: maintainability, small functions, testing seams, refactoring legacy code

The main goal is not just to make the old integration work again. The goal is to build a clean, modern, typed, tested Python module first, and then make the Home Assistant integration a thin adapter around that module.

## High-level goal

Create a standalone Python package for Munich public transport data, then integrate it into Home Assistant.

The standalone client should know nothing about Home Assistant.

The Home Assistant integration should know as little as possible about the underlying transport API. It should use the standalone client and expose the result via Home Assistant entities.

## Important design principle

Do not write Java-shaped Python.

Use Java/software-engineering lessons where they make sense:

- separation of concerns
- explicit boundaries
- dependency inversion
- testability
- domain modeling
- meaningful exceptions
- immutable value objects where useful

But express them idiomatically in Python:

- small functions are fine
- dataclasses instead of boilerplate POJOs
- protocols instead of heavy abstract class hierarchies
- dependency injection without a framework/container
- composition over inheritance
- pytest function-style tests
- no unnecessary factories/builders/managers

## Target architecture

Preferred structure for the standalone package:

```text
munich_transport/
  pyproject.toml
  README.md
  src/
    munich_transport/
      __init__.py
      client.py          # public async client API
      models.py          # domain models: Station, Departure, etc.
      parser.py          # pure JSON/raw-response -> model conversion
      transport.py       # HTTP transport abstraction + implementation
      exceptions.py      # custom exceptions
      types.py           # optional shared typing aliases/enums
  tests/
    fixtures/
      station_search_*.json
      departures_*.json
      api_error_*.json
    test_parser.py
    test_client.py
    test_transport.py
