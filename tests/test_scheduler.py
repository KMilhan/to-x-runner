from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

import unirun.scheduler as scheduler
from unirun import Run, RuntimeConfig, thread_executor
from unirun.scheduler import ExecutorLease


def test_run_threads_scope_shuts_down() -> None:
    scope = Run(flavor="threads", max_workers=1, trace=True)
    with scope as executor:
        assert executor.submit(lambda: 41 + 1).result() == 42
    assert scope.trace is not None
    with pytest.raises(RuntimeError):
        executor.submit(lambda: 1)


def test_run_nested_reuses_executor() -> None:
    outer = Run(flavor="threads", max_workers=2, trace=True)
    with outer as outer_executor:
        inner = Run(flavor="threads", trace=True)
        with inner as inner_executor:
            assert inner_executor is outer_executor
        assert inner.trace is not None
    assert outer.trace is not None


def test_run_with_provided_executor_not_shutdown() -> None:
    provided = ThreadPoolExecutor(max_workers=1)
    scope = Run(flavor="threads", executor=provided)
    with scope as executor:
        assert executor is provided
        assert executor.submit(lambda: "ok").result() == "ok"
    # Executor should remain usable because caller owns lifecycle.
    assert provided.submit(lambda: 3).result() == 3
    provided.shutdown()


def test_run_trace_capture() -> None:
    scope = Run(flavor="threads", trace=True)
    with scope:
        pass
    assert scope.trace is not None
    assert scope.trace.resolved_mode in {"thread", "none"}


def test_scheduler_get_executor_explicit_mode() -> None:
    executor = scheduler.get_executor(mode="thread")
    assert executor is thread_executor()


def test_scheduler_lease_executor_processes() -> None:
    lease: ExecutorLease = scheduler.lease_executor(mode="process")
    assert isinstance(lease.executor, ProcessPoolExecutor)
    assert lease.owns_executor is True
    lease.executor.shutdown()


def test_scheduler_executor_for_unknown_mode_defaults_to_thread() -> None:
    base_scheduler = scheduler.Scheduler()
    executor = base_scheduler._executor_for_mode(
        "unknown",
        {},
        config=base_scheduler.config,
        leased=False,
        thread_mode=None,
        name=None,
    )
    assert executor is thread_executor()


def test_scheduler_reason_for_provided_mode() -> None:
    base_scheduler = scheduler.Scheduler()
    reason = base_scheduler._reason_for("provided", {})
    assert reason == "used caller-provided executor"


def test_scheduler_config_property() -> None:
    local_scheduler = scheduler.Scheduler()
    assert isinstance(local_scheduler.config, RuntimeConfig)
