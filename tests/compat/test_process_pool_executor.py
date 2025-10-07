from __future__ import annotations

import math
import multiprocessing as mp
import os
import sys
from concurrent.futures import ProcessPoolExecutor as StdProcessPoolExecutor
from typing import Iterator

import pytest

from unirun import last_decision, reset
from unirun.compat import ProcessPoolExecutor


@pytest.fixture(autouse=True)
def reset_scheduler() -> Iterator[None]:
    """Reset managed pools so process workers do not leak between tests."""
    reset(cancel_futures=True)
    yield
    reset(cancel_futures=True)


@pytest.mark.skipif(sys.platform == "win32", reason="process pools are flaky on windows CI")
def test_process_pool_executor_resolves_via_scheduler() -> None:
    """Compat executor should honour scheduler heuristics for processes."""
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(math.sqrt, 16)
        assert future.result() == pytest.approx(4.0)

    trace = last_decision()
    assert trace is not None
    assert trace.resolved_mode == "process"


@pytest.mark.skipif(sys.platform == "win32", reason="process pools are flaky on windows CI")
def test_process_pool_executor_initializer_requests_stdlib() -> None:
    """Initializer support is routed through the stdlib pool implementation."""
    context = mp.get_context("spawn")

    with ProcessPoolExecutor(initializer=os.getpid, max_workers=1, mp_context=context) as executor:
        future = executor.submit(math.sqrt, 9)
        assert future.result() == pytest.approx(3.0)
        assert isinstance(executor.delegate, StdProcessPoolExecutor)

    assert last_decision() is None
