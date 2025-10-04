from __future__ import annotations

import asyncio
import math
import time
from concurrent.futures import ProcessPoolExecutor

from unirun import to_process, to_thread
from unirun.workloads import count_primes, simulate_blocking_io


def test_to_thread_matches_asyncio_to_thread() -> None:
    async def runner() -> None:
        start = time.perf_counter()
        value = await to_thread(simulate_blocking_io, 0.01)
        elapsed = time.perf_counter() - start
        assert math.isclose(value, 0.01, rel_tol=0.3, abs_tol=0.03)
        assert elapsed >= 0.01
        stdlib_value = await asyncio.to_thread(simulate_blocking_io, 0.01)
        assert value == stdlib_value

    asyncio.run(runner())


def test_to_process_matches_loop_executor() -> None:
    async def runner() -> None:
        result = await to_process(count_primes, 200)
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=1) as pool:
            expected = await loop.run_in_executor(pool, count_primes, 200)
        assert result == expected

    asyncio.run(runner())
