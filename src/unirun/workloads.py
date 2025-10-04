from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Iterable


def count_primes(limit: int) -> int:
    """Naively count prime numbers below ``limit``.

    The implementation intentionally uses a simple algorithm so it spends a
    meaningful amount of CPU time without relying on third-party packages.
    """

    if limit < 2:
        return 0
    primes: list[int] = []
    for candidate in range(2, limit):
        is_prime = True
        root = int(math.isqrt(candidate))
        for divisor in primes:
            if divisor > root:
                break
            if candidate % divisor == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(candidate)
    return len(primes)


def simulate_blocking_io(duration: float) -> float:
    """Sleep for ``duration`` seconds to emulate blocking IO."""

    time.sleep(duration)
    return duration


async def simulate_async_io(duration: float) -> float:
    """Asyncio-friendly sleep used to benchmark async workflows."""

    await asyncio.sleep(duration)
    return duration


def mixed_workload(pairs: Iterable[tuple[int, float]]) -> list[float]:
    """Run alternating CPU and IO segments sequentially."""

    results: list[float] = []
    for limit, duration in pairs:
        primes = count_primes(limit)
        time.sleep(duration)
        results.append(primes / (duration + 1e-6))
    return results


__all__ = [
    "count_primes",
    "simulate_blocking_io",
    "simulate_async_io",
    "mixed_workload",
]
