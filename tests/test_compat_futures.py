from __future__ import annotations

import importlib
import sys
from concurrent.futures import ThreadPoolExecutor as StdThreadPoolExecutor
from types import ModuleType

import pytest

from unirun import scheduler


def _reload_futures(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> ModuleType:
    monkeypatch.setenv("UNIRUN_COMPAT_MODE", mode)
    for name in list(sys.modules):
        if name.startswith("unirun.compat"):
            sys.modules.pop(name)
    return importlib.import_module("unirun.compat.concurrent.futures")


def test_thread_pool_executor_runs() -> None:
    from unirun.compat.concurrent import futures as compat_futures

    with compat_futures.ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(lambda: 21 * 2)
        assert future.result() == 42
        # Decision trace is available when managed by unirun.
        decision = getattr(executor, "decision", None)
        if decision is not None:
            assert decision.resolved_mode in {"thread", "threads", "none"}


def test_process_pool_executor_runs() -> None:
    from unirun.compat.concurrent import futures as compat_futures

    with compat_futures.ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda value: value + 1, 41)
        assert future.result() == 42


def test_passthrough_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from unirun.compat.concurrent import futures as compat_futures

    compat_passthrough = _reload_futures(monkeypatch, "passthrough")

    tp_executor = compat_passthrough.ThreadPoolExecutor  # type: ignore[attr-defined]
    assert tp_executor is not compat_futures.ThreadPoolExecutor
    with tp_executor(max_workers=1) as executor:
        assert executor.submit(lambda: 40 + 2).result() == 42

    monkeypatch.delenv("UNIRUN_COMPAT_MODE")
    _reload_futures(monkeypatch, "managed")


def test_thread_pool_executor_initializer_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unirun.compat.concurrent import futures as compat_futures

    calls: list[int] = []

    def init() -> None:
        calls.append(1)

    warning = "initializer requires stdlib executor"
    with pytest.warns(RuntimeWarning, match=warning):
        with compat_futures.ThreadPoolExecutor(initializer=init) as executor:
            assert executor.submit(lambda: 1).result() == 1
    assert calls


def test_process_executor_warns_on_scheduler_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unirun.compat.concurrent import futures as compat_futures

    def fake_lease_executor(*args, **kwargs):
        executor = StdThreadPoolExecutor(max_workers=1)
        trace = scheduler.DecisionTrace(
            mode="processes",
            hints={},
            resolved_mode="thread",
            reason="forced to thread pool via configuration",
        )
        return scheduler.ExecutorLease(
            executor=executor,
            owns_executor=True,
            trace=trace,
        )

    monkeypatch.setattr(compat_futures.scheduler, "lease_executor", fake_lease_executor)

    match = "thread pool via configuration"
    with pytest.warns(RuntimeWarning, match=match):
        with compat_futures.ProcessPoolExecutor(max_workers=1):
            pass


def test_observe_decisions_with_compat_executor(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from unirun.compat.concurrent import futures as compat_futures

    caplog.set_level("INFO", logger="unirun.scheduler")
    with scheduler.observe_decisions():
        with compat_futures.ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(lambda: 2).result() == 2
    assert "scheduler resolved" in caplog.text
