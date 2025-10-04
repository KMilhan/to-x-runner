from __future__ import annotations

from concurrent.futures import Future

from unirun import submit, thread_executor
from unirun.executors.threading import get_thread_pool, reset_thread_pool
from unirun.workloads import simulate_blocking_io


def test_thread_executor_returns_singleton() -> None:
    first = thread_executor()
    second = thread_executor()
    assert first is second


def test_thread_executor_reconfigures_on_max_workers_hint() -> None:
    baseline = thread_executor(max_workers=1)
    updated = thread_executor(max_workers=3)
    assert baseline is not updated
    assert getattr(updated, "_max_workers", None) == 3


def test_submit_returns_future() -> None:
    executor = thread_executor()
    future = submit(executor, simulate_blocking_io, 0.0)
    assert isinstance(future, Future)
    assert future.result() == 0.0
    comparison = executor.submit(simulate_blocking_io, 0.0).result()
    assert future.result() == comparison


def test_thread_executor_reconfigures_on_prefix_change() -> None:
    reset_thread_pool()
    baseline = get_thread_pool()
    updated = get_thread_pool(thread_name_prefix="custom-prefix")
    assert updated is not baseline
