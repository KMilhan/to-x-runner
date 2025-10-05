from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor

import pytest

from unirun import process_executor
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process pool parity test skipped on Windows",
)
@pytest.mark.skipif(
    _mutation_instrumentation_active(),
    reason="mutmut instrumentation is incompatible with multiprocessing trampolines",
)
def test_process_executor_matches_stdlib() -> None:
    executor = process_executor(max_workers=1)
    result = executor.submit(count_primes, 300).result()
    with ProcessPoolExecutor(max_workers=1) as pool:
        expected = pool.submit(count_primes, 300).result()
    assert result == expected
