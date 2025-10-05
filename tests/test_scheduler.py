from __future__ import annotations

import dataclasses
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

import unirun.scheduler as scheduler
from unirun import Run, RuntimeConfig, thread_executor
from unirun.executors import subinterpreter
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


def test_scheduler_config_property() -> None:
    local_scheduler = scheduler.Scheduler()
    assert isinstance(local_scheduler.config, RuntimeConfig)


def test_scheduler_force_threads_configuration() -> None:
    config = RuntimeConfig(force_threads=True)
    base_scheduler = scheduler.Scheduler(config=config)
    executor = base_scheduler.get_executor()
    assert executor is thread_executor()
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "thread"
    assert "forced" in trace.reason


def test_scheduler_force_process_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    config = RuntimeConfig(force_process=True)
    base_scheduler = scheduler.Scheduler(config=config)
    sentinel = object()

    monkeypatch.setattr(scheduler, "get_process_pool", lambda **_: sentinel)
    executor = base_scheduler.get_executor()
    assert executor is sentinel
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "process"
    assert "forced" in trace.reason


def test_scheduler_thread_mode_gil_on_free_threaded_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = RuntimeConfig(thread_mode="gil")
    base_scheduler = scheduler.Scheduler(config=config)
    caps = base_scheduler.capabilities
    base_scheduler._capabilities = dataclasses.replace(
        caps,
        gil_enabled=False,
        free_threading_build=True,
    )
    sentinel = object()
    monkeypatch.setattr(scheduler, "get_process_pool", lambda **_: sentinel)
    executor = base_scheduler.get_executor()
    assert executor is sentinel
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "process"
    assert "gil" in trace.reason


def test_scheduler_thread_mode_nogil_on_gil_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = RuntimeConfig(thread_mode="nogil")
    base_scheduler = scheduler.Scheduler(config=config)
    caps = base_scheduler.capabilities
    base_scheduler._capabilities = dataclasses.replace(
        caps,
        gil_enabled=True,
        free_threading_build=False,
    )
    sentinel = object()
    monkeypatch.setattr(scheduler, "get_thread_pool", lambda **_: sentinel)
    executor = base_scheduler.get_executor()
    assert executor is sentinel
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "thread"
    assert "nogil" in trace.reason


def test_scheduler_subinterpreter_fallback_updates_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = RuntimeConfig(prefers_subinterpreters=True)
    base_scheduler = scheduler.Scheduler(config=config)
    caps = base_scheduler.capabilities
    base_scheduler._capabilities = dataclasses.replace(
        caps,
        supports_subinterpreters=True,
    )

    def raising(**_: object) -> subinterpreter.SubInterpreterExecutor:
        raise subinterpreter.SubInterpreterUnavailable("boom")

    monkeypatch.setattr(scheduler, "SubInterpreterExecutor", raising)

    lease = base_scheduler.lease_executor(mode="auto")
    assert base_scheduler.trace is not None
    assert base_scheduler.trace.resolved_mode == "thread"
    assert "fell back" in base_scheduler.trace.reason
    lease.executor.shutdown(wait=True)


def test_scheduler_decision_listener() -> None:
    captured: list[scheduler.DecisionTrace] = []
    scheduler.add_decision_listener(captured.append)
    scheduler.get_executor()
    assert len(captured) == 1
    scheduler.remove_decision_listener(captured.append)


def test_scheduler_observe_decisions(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="unirun.scheduler")
    with scheduler.observe_decisions():
        scheduler.get_executor()

    assert "scheduler resolved" in caplog.text


def test_scheduler_observe_decisions_custom_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("unirun.test-observe")
    caplog.set_level(logging.DEBUG, logger="unirun.test-observe")

    with scheduler.observe_decisions(logger=logger, level=logging.DEBUG):
        scheduler.get_executor()

    assert "scheduler resolved" in caplog.text
