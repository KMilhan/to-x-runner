from __future__ import annotations

import threading
from typing import Iterator

import pytest

from unirun import last_decision, reset
from unirun.compat import ThreadPoolExecutor


@pytest.fixture(autouse=True)
def reset_scheduler() -> Iterator[None]:
    """Ensure pools are fresh for every test to avoid cross-test bleed."""
    reset(cancel_futures=True)
    yield
    reset(cancel_futures=True)


def test_thread_pool_executor_records_scheduler_trace() -> None:
    """Compat executor should leave a scheduler trace for observability."""
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="compat-thread") as executor:
        future = executor.submit(lambda: threading.current_thread().name)
        thread_name = future.result()

    trace = last_decision()
    assert trace is not None
    assert trace.resolved_mode == "thread"
    assert "compat-thread" in thread_name


def test_thread_pool_executor_initializer_triggers_stdlib_fallback() -> None:
    """Initializers require the stdlib executor for feature parity."""
    seen: list[str] = []

    def _initializer() -> None:
        seen.append(threading.current_thread().name)

    with ThreadPoolExecutor(initializer=_initializer) as executor:
        executor.submit(lambda: None).result()

    assert seen
