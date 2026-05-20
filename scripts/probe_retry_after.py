"""Bounded live probe for MVG transient responses and Retry-After headers.

This script is intentionally capped and delayed. It is for occasional manual
diagnostics only, not for normal test runs.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

import aiohttp

TRANSIENT_STATUSES = frozenset({429, 502, 503, 504})
DEFAULT_ENDPOINT = "https://www.mvg.de/api/bgw-pt/v3/departures"
DEFAULT_PARAMS = {
    "globalId": "de:09162:2",
    "limit": "1",
    "transportTypes": "UBAHN,TRAM,SBAHN,BUS,REGIONAL_BUS,BAHN",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-attempts", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")
    if args.delay < 0.1:
        parser.error("--delay must be at least 0.1 seconds")

    found = asyncio.run(
        _run(
            max_attempts=args.max_attempts,
            delay_seconds=args.delay,
            timeout_seconds=args.timeout,
        )
    )
    return 0 if found else 1


async def _run(
    *,
    max_attempts: int,
    delay_seconds: float,
    timeout_seconds: float,
) -> bool:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    status_counts: dict[int, int] = {}

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for attempt in range(1, max_attempts + 1):
            async with session.get(DEFAULT_ENDPOINT, params=DEFAULT_PARAMS) as response:
                body = await response.text()
                status_counts[response.status] = (
                    status_counts.get(response.status, 0) + 1
                )

                if response.status in TRANSIENT_STATUSES:
                    print(f"transient attempt={attempt} status={response.status}")
                    print(f"retry-after={response.headers.get('Retry-After')!r}")
                    print(f"cache-control={response.headers.get('Cache-Control')!r}")
                    print(f"content-type={response.headers.get('Content-Type')!r}")
                    print(f"body-prefix={body[:300]!r}")
                    return True

            await asyncio.sleep(delay_seconds)

    print(f"no transient response after {max_attempts} requests")
    print(f"statuses={status_counts}")
    return False


if __name__ == "__main__":
    raise SystemExit(main())
