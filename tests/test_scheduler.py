from __future__ import annotations

import dataclasses

import pytest

import unirun.scheduler as scheduler
from unirun import (
    RuntimeConfig,
    get_executor,
    last_decision,
    process_executor,
    reset,
    run,
    thread_executor,
)
from unirun.executors import subinterpreter
from unirun.workloads import count_primes, simulate_blocking_io


def test_run_cpu_bound_prefers_process_executor() -> None:
    result = run(count_primes, 1_000, cpu_bound=True)
    assert result == 168
    trace = scheduler._GLOBAL_SCHEDULER.trace
    assert trace is not None
    caps = scheduler._GLOBAL_SCHEDULER.capabilities
    expected_mode = "thread" if (not caps.gil_enabled or caps.free_threading_build) else "process"
    assert trace.resolved_mode == expected_mode


def test_run_io_bound_uses_thread_executor() -> None:
    result = run(simulate_blocking_io, 0.0, io_bound=True)
    assert result == 0.0
    trace = scheduler._GLOBAL_SCHEDULER.trace
    assert trace is not None
    assert trace.resolved_mode == "thread"


def test_get_executor_explicit_mode() -> None:
    executor = get_executor(mode="thread")
    assert executor is thread_executor()


def test_reset_clears_trace_and_pools() -> None:
    run(simulate_blocking_io, 0.0, io_bound=True)
    assert scheduler._GLOBAL_SCHEDULER.trace is not None
    reset()
    assert scheduler._GLOBAL_SCHEDULER.trace is None


def test_last_decision_helper() -> None:
    run(lambda: "value")
    trace = last_decision()
    assert trace is not None
    assert trace.as_dict()["resolved_mode"] == "thread"


def test_provided_executor_trace() -> None:
    scheduler.reset()
    executor = thread_executor()
    result = scheduler.get_executor(mode="auto", executor=executor)
    assert result is executor
    trace = scheduler._GLOBAL_SCHEDULER.trace
    assert trace is not None
    assert trace.reason == "caller supplied executor instance"


def test_none_mode_resolves_to_thread() -> None:
    scheduler.reset()
    executor = scheduler.get_executor(mode="none")
    assert executor is thread_executor()
    trace = scheduler._GLOBAL_SCHEDULER.trace
    assert trace is not None
    assert trace.reason == "automation disabled; defaulting to shared thread pool"


def test_config_override_forces_process() -> None:
    config = RuntimeConfig(auto=False, mode="process", max_workers=1)
    local_scheduler = scheduler.Scheduler(config=config)
    executor = local_scheduler.get_executor()
    assert executor is process_executor()
    trace = local_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "process"
    assert trace.reason == "cpu-bound hints or GIL-enabled runtime suggested process pool"


def test_prefers_subinterpreter_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    base_scheduler = scheduler.Scheduler()
    caps = base_scheduler.capabilities
    patched_caps = dataclasses.replace(
        caps,
        supports_subinterpreters=True,
        gil_enabled=True,
        free_threading_build=False,
    )
    base_scheduler._capabilities = patched_caps
    fake_executor = object()
    monkeypatch.setattr(subinterpreter, "get_interpreter_executor", lambda **_: fake_executor)
    monkeypatch.setattr(scheduler, "get_interpreter_executor", lambda **_: fake_executor)
    executor = base_scheduler.get_executor(prefers_subinterpreters=True)
    assert executor is fake_executor
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "subinterpreter"
    assert trace.reason == "caller requested sub-interpreters and runtime supports them"


def test_cpu_bound_free_threading_prefers_thread() -> None:
    base_scheduler = scheduler.Scheduler()
    caps = base_scheduler.capabilities
    patched_caps = dataclasses.replace(caps, gil_enabled=False, free_threading_build=True)
    base_scheduler._capabilities = patched_caps
    executor = base_scheduler.get_executor(cpu_bound=True)
    assert executor is thread_executor()
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "thread"
    assert trace.reason == "io-bound or free-threaded runtime prefers thread pool"


def test_config_mode_preference() -> None:
    config = RuntimeConfig(mode="thread")
    base_scheduler = scheduler.Scheduler(config=config)
    executor = base_scheduler.get_executor()
    assert executor is thread_executor()
    trace = base_scheduler.trace
    assert trace is not None
    assert trace.resolved_mode == "thread"


def test_executor_for_unknown_mode_defaults_to_thread() -> None:
    base_scheduler = scheduler.Scheduler()
    executor = base_scheduler._executor_for_mode("unknown", {})
    assert executor is thread_executor()


def test_reason_for_provided_mode() -> None:
    base_scheduler = scheduler.Scheduler()
    reason = base_scheduler._reason_for("provided", {})
    assert reason == "used caller-provided executor"


def test_scheduler_config_property() -> None:
    local_scheduler = scheduler.Scheduler()
    assert isinstance(local_scheduler.config, RuntimeConfig)
