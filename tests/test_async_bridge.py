from __future__ import annotations

import asyncio
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from threading import current_thread

import pytest

from unirun import thread_executor, to_process, to_thread, wrap_future
from unirun.workloads import simulate_async_io, simulate_blocking_io


def test_to_thread_uses_shared_executor() -> None:
    async def capture_name() -> str:
        return await to_thread(lambda: current_thread().name)

    name = asyncio.run(capture_name())
    assert name.startswith("unirun-thread")


@pytest.mark.skipif(sys.platform == "win32", reason="process pool not exercised on Windows in tests")
def test_to_process_runs_function() -> None:
    async def runner() -> None:
        result = await to_process(simulate_blocking_io, 0.0)
        assert math.isclose(result, 0.0)
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=1) as pool:
            expected = await loop.run_in_executor(pool, simulate_blocking_io, 0.0)
        assert math.isclose(expected, 0.0)

    asyncio.run(runner())


def test_wrap_future_converts_future() -> None:
    async def runner() -> None:
        executor = thread_executor()
        future = executor.submit(simulate_blocking_io, 0.0)
        wrapped = wrap_future(future)
        assert await wrapped == 0.0
        with ThreadPoolExecutor() as pool:
            std_future = pool.submit(simulate_blocking_io, 0.0)
            assert await asyncio.wrap_future(std_future) == 0.0

    asyncio.run(runner())


def test_simulate_async_workload() -> None:
    async def runner() -> None:
        start = time.perf_counter()
        result = await simulate_async_io(0.01)
        elapsed = time.perf_counter() - start
        assert math.isclose(result, 0.01, rel_tol=0.3, abs_tol=0.03)
        assert elapsed >= 0.01

    asyncio.run(runner())
