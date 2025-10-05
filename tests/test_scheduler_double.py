from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from unirun import Run, RuntimeConfig, configure, thread_executor
from unirun import map as unirun_map
from unirun.workloads import count_primes


def _mutation_instrumentation_active() -> bool:
    """Detect whether mutmut instrumentation is active in the current process."""

    module = sys.modules.get("mutmut")
    if module is None:
        return False
    config = getattr(module, "config", None)
    if config is None:
        return True
    return bool(getattr(config, "is_running", True))


def test_run_matches_threadpool_executor() -> None:
    configure(RuntimeConfig(mode="thread", auto=False))
    run_scope = Run(flavor="threads", max_workers=1)
    with run_scope as executor:
        value = executor.submit(count_primes, 200).result()
    with ThreadPoolExecutor(max_workers=1) as pool:
        expected = pool.submit(count_primes, 200).result()
    assert value == expected


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process pool parity test skipped on Windows",
)
@pytest.mark.skipif(
    _mutation_instrumentation_active(),
    reason="mutmut instrumentation is incompatible with multiprocessing trampolines",
)
def test_run_matches_process_pool() -> None:
    configure(RuntimeConfig(mode="process", auto=False))
    run_scope = Run(flavor="processes", max_workers=1)
    with run_scope as executor:
        value = executor.submit(count_primes, 300).result()
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
