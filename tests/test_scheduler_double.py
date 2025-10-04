from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from unirun import RuntimeConfig, configure, run, thread_executor
from unirun import map as unirun_map
from unirun.workloads import count_primes


def test_run_matches_threadpool_executor() -> None:
    configure(RuntimeConfig(mode="thread", auto=False))
    value = run(count_primes, 200, mode="thread")
    with ThreadPoolExecutor(max_workers=1) as pool:
        expected = pool.submit(count_primes, 200).result()
    assert value == expected


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process pool parity test skipped on Windows",
)
def test_run_matches_process_pool() -> None:
    configure(RuntimeConfig(mode="process", auto=False))
    value = run(count_primes, 300, mode="process")
    with ProcessPoolExecutor(max_workers=1) as pool:
        expected = pool.submit(count_primes, 300).result()
    assert value == expected


def test_map_matches_stdlib() -> None:
    configure(RuntimeConfig(mode="thread", auto=False))
    data = ["a", "b", "c"]
    with ThreadPoolExecutor() as pool:
        expected = list(pool.map(str.upper, data))
    results = list(unirun_map(thread_executor(), str.upper, data))
    assert results == expected
