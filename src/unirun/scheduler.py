from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from .capabilities import RuntimeCapabilities, detect_capabilities
from .config import RuntimeConfig, ThreadMode
from .executors import async_bridge
from .executors.process import get_process_pool, reset_process_pool
from .executors.subinterpreter import (
    SubInterpreterExecutor,
    SubInterpreterUnavailable,
    get_interpreter_executor,
    reset_interpreter_executor,
)
from .executors.threading import get_thread_pool, reset_thread_pool


@dataclass(slots=True)
class DecisionTrace:
    mode: str
    hints: dict[str, Any]
    resolved_mode: str
    reason: str
    thread_mode: ThreadMode | None = None
    name: str | None = None
    max_workers: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Represent the trace as plain data for logging or testing."""

        return {
            "mode": self.mode,
            "hints": dict(self.hints),
            "resolved_mode": self.resolved_mode,
            "reason": self.reason,
            "thread_mode": self.thread_mode,
            "name": self.name,
            "max_workers": self.max_workers,
        }


@dataclass(slots=True)
class ExecutorLease:
    executor: Executor
    owns_executor: bool
    trace: DecisionTrace


class Scheduler:
    """Co-ordinates executor selection while keeping stdlib semantics."""

    def __init__(self, *, config: RuntimeConfig | None = None) -> None:
        self._config = config or RuntimeConfig.from_env()
        self._capabilities: RuntimeCapabilities = detect_capabilities()
        self._trace: DecisionTrace | None = None
        self._listeners: list[Callable[[DecisionTrace], None]] = []
        self._last_fallback_reason: str | None = None
        self._last_fallback_mode: str | None = None

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return self._capabilities

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    @property
    def trace(self) -> DecisionTrace | None:
        """Return the most recent decision trace for observability."""

        return self._trace

    def refresh_capabilities(self) -> None:
        self._capabilities = detect_capabilities()

    def configure(self, config: RuntimeConfig) -> None:
        """Replace the scheduler configuration and refresh capabilities."""

        self._config = config
        self.refresh_capabilities()
        self._trace = None

    def get_executor(self, mode: str = "auto", **hints: Any) -> Executor:
        if "executor" in hints and isinstance(hints["executor"], Executor):
            provided = hints["executor"]
            self._trace = DecisionTrace(
                mode=mode,
                hints=hints,
                resolved_mode="provided",
                reason="caller supplied executor instance",
            )
            return provided

        self._last_fallback_reason = None
        self._last_fallback_mode = None

        resolved_mode, reason, effective_thread_mode = self._resolve_mode(
            mode,
            hints,
            self._config,
        )
        executor = self._executor_for_mode(
            resolved_mode,
            hints,
            config=self._config,
            leased=False,
            thread_mode=effective_thread_mode,
            name=hints.get("name"),
        )
        actual_mode = self._last_fallback_mode or resolved_mode
        if self._last_fallback_reason and self._last_fallback_mode is None:
            actual_mode = "thread"
        actual_reason = (
            f"{reason}; {self._last_fallback_reason}"
            if self._last_fallback_reason
            else reason
        )
        self._trace = DecisionTrace(
            mode=mode,
            hints=hints,
            resolved_mode=actual_mode,
            reason=actual_reason,
            thread_mode=effective_thread_mode,
            name=hints.get("name"),
            max_workers=hints.get("max_workers"),
        )
        self._notify_listeners(self._trace)
        return executor

    def lease_executor(
        self,
        mode: str = "auto",
        *,
        runtime_config: RuntimeConfig | None = None,
        executor: Executor | None = None,
        max_workers: int | None = None,
        name: str | None = None,
        thread_mode: ThreadMode | None = None,
    ) -> ExecutorLease:
        hints: dict[str, Any] = {}
        if executor is not None:
            trace = DecisionTrace(
                mode=mode,
                hints={"executor": executor},
                resolved_mode="provided",
                reason="caller supplied executor instance",
                thread_mode=thread_mode,
                name=name,
                max_workers=max_workers,
            )
            self._trace = trace
            return ExecutorLease(executor=executor, owns_executor=False, trace=trace)

        active_config = runtime_config or self._config
        hints.update(
            {
                "max_workers": max_workers,
                "name": name,
                "thread_mode": thread_mode or active_config.thread_mode,
                "prefers_subinterpreters": active_config.prefers_subinterpreters,
            }
        )

        self._last_fallback_reason = None
        self._last_fallback_mode = None

        resolved_mode, reason, effective_thread_mode = self._resolve_mode(
            mode,
            hints,
            active_config,
        )
        executor_obj = self._executor_for_mode(
            resolved_mode,
            hints,
            config=active_config,
            leased=True,
            thread_mode=effective_thread_mode,
            name=name,
        )
        actual_mode = self._last_fallback_mode or resolved_mode
        if self._last_fallback_reason and self._last_fallback_mode is None:
            actual_mode = "thread"
        actual_reason = (
            f"{reason}; {self._last_fallback_reason}"
            if self._last_fallback_reason
            else reason
        )
        trace = DecisionTrace(
            mode=mode,
            hints=hints,
            resolved_mode=actual_mode,
            reason=actual_reason,
            thread_mode=effective_thread_mode,
            name=name,
            max_workers=max_workers,
        )
        self._trace = trace
        self._notify_listeners(trace)
        return ExecutorLease(executor=executor_obj, owns_executor=True, trace=trace)

    def reset(self, *, cancel_futures: bool = False) -> None:
        reset_thread_pool(cancel_futures=cancel_futures)
        reset_process_pool(cancel_futures=cancel_futures)
        reset_interpreter_executor(cancel_futures=cancel_futures)
        self.refresh_capabilities()
        self._trace = None

    def _resolve_mode(
        self,
        mode: str,
        hints: dict[str, Any],
        config: RuntimeConfig,
    ) -> tuple[str, str, ThreadMode]:
        effective_thread_mode: ThreadMode = (
            hints.get("thread_mode") or config.thread_mode
        )
        force_threads = bool(hints.get("force_threads")) or config.force_threads
        force_process = bool(hints.get("force_process")) or config.force_process
        prefer_sub = hints.get(
            "prefers_subinterpreters",
            config.prefers_subinterpreters,
        )
        cpu_bound = hints.get("cpu_bound", config.cpu_bound)
        io_bound = hints.get("io_bound", config.io_bound)

        if force_threads and force_process:
            force_process = False

        if force_threads:
            return (
                "thread",
                "forced to thread pool via configuration",
                effective_thread_mode,
            )
        if force_process:
            return (
                "process",
                "forced to process pool via configuration",
                effective_thread_mode,
            )

        if not config.auto:
            if mode != "auto":
                return (
                    mode,
                    "automation disabled; respecting requested mode",
                    effective_thread_mode,
                )
            if config.mode != "auto":
                return (
                    config.mode,
                    "automation disabled via runtime config",
                    effective_thread_mode,
                )
            return (
                "none",
                "automation disabled; defaulting to shared thread pool",
                effective_thread_mode,
            )

        if mode == "none":
            return (
                "none",
                "caller requested shared thread pool",
                effective_thread_mode,
            )
        if mode != "auto":
            return (
                mode,
                "caller requested explicit mode",
                effective_thread_mode,
            )

        if config.mode != "auto":
            return (
                config.mode,
                "runtime config pinned executor mode",
                effective_thread_mode,
            )

        if prefer_sub and self._capabilities.supports_subinterpreters:
            return (
                "subinterpreter",
                "runtime supports sub-interpreters and preference set",
                effective_thread_mode,
            )

        if cpu_bound:
            if self._threads_parallel(effective_thread_mode):
                return (
                    "thread",
                    self._thread_reason(effective_thread_mode, cpu_bound=True),
                    effective_thread_mode,
                )
            return (
                "process",
                "cpu-bound workload prefers process pool",
                effective_thread_mode,
            )

        if io_bound:
            return (
                "thread",
                "io-bound workload prefers thread pool",
                effective_thread_mode,
            )

        if effective_thread_mode == "gil":
            return (
                "process",
                "thread mode forced to 'gil'; using process pool",
                effective_thread_mode,
            )

        if self._threads_parallel(effective_thread_mode):
            return (
                "thread",
                self._thread_reason(effective_thread_mode, cpu_bound=False),
                effective_thread_mode,
            )

        if prefer_sub and self._capabilities.supports_subinterpreters:
            return (
                "subinterpreter",
                "runtime supports sub-interpreters and preference set",
                effective_thread_mode,
            )

        return (
            "thread",
            "defaulted to shared thread pool",
            effective_thread_mode,
        )

    def _executor_for_mode(
        self,
        mode: str,
        hints: dict[str, Any],
        *,
        config: RuntimeConfig,
        leased: bool,
        thread_mode: ThreadMode | None,
        name: str | None,
    ) -> Executor:
        if mode == "none":
            if leased:
                prefix = self._thread_prefix(name, thread_mode)
                return ThreadPoolExecutor(
                    max_workers=hints.get("max_workers"),
                    thread_name_prefix=prefix,
                )
            return get_thread_pool(
                max_workers=hints.get("max_workers"),
                thread_name_prefix=name,
            )
        if mode == "thread":
            configured_workers = config.max_workers
            suggested_workers = self._capabilities.suggested_io_workers
            max_workers = hints.get(
                "max_workers",
                configured_workers or suggested_workers,
            )
            if leased:
                prefix = self._thread_prefix(name, thread_mode)
                return ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=prefix,
                )
            return get_thread_pool(max_workers=max_workers, thread_name_prefix=name)
        if mode == "process":
            configured_workers = config.max_workers
            suggested_workers = self._capabilities.suggested_process_workers
            max_workers = hints.get(
                "max_workers",
                configured_workers or suggested_workers,
            )
            if leased:
                return ProcessPoolExecutor(max_workers=max_workers)
            return get_process_pool(max_workers=max_workers)
        if mode == "subinterpreter":
            if leased:
                isolated = hints.get("isolated", True)
                try:
                    return SubInterpreterExecutor(
                        max_workers=hints.get("max_workers"),
                        isolated=isolated,
                    )
                except SubInterpreterUnavailable:
                    # Fallback to shared thread pool when interpreters missing.
                    self._last_fallback_reason = (
                        "sub-interpreters unavailable; fell back to thread pool"
                    )
                    self._last_fallback_mode = "thread"
                    return self._executor_for_mode(
                        "thread",
                        hints,
                        config=config,
                        leased=leased,
                        thread_mode=thread_mode,
                        name=name,
                    )
            return get_interpreter_executor(max_workers=hints.get("max_workers"))
        if mode == "provided":  # pragma: no cover - guardrail
            raise RuntimeError("Provided mode is reserved for user-supplied executors")
        # Default to thread pool for safety.
        if leased:
            prefix = self._thread_prefix(name, thread_mode)
            return ThreadPoolExecutor(
                max_workers=hints.get("max_workers"),
                thread_name_prefix=prefix,
            )
        return get_thread_pool(
            max_workers=hints.get("max_workers"),
            thread_name_prefix=name,
        )

    def _thread_prefix(
        self,
        name: str | None,
        thread_mode: ThreadMode | None,
    ) -> str:
        if name:
            return name
        if thread_mode == "nogil":
            return "unirun-run-thread-nogil"
        if thread_mode == "gil":
            return "unirun-run-thread-gil"
        return "unirun-run-thread"

    def _threads_parallel(self, thread_mode: ThreadMode) -> bool:
        if thread_mode == "nogil":
            return True
        if thread_mode == "gil":
            return False
        return (not self._capabilities.gil_enabled) or (
            self._capabilities.free_threading_build
        )

    def _thread_reason(self, thread_mode: ThreadMode, *, cpu_bound: bool) -> str:
        if thread_mode == "nogil":
            base = "thread mode forced to 'nogil'"
        elif (not self._capabilities.gil_enabled) or (
            self._capabilities.free_threading_build
        ):
            base = "free-threaded runtime can run threads in parallel"
        else:
            base = "thread pool selected by heuristics"
        if cpu_bound:
            return f"{base} for cpu-bound workload"
        return base

    def add_listener(self, listener: Callable[[DecisionTrace], None]) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[DecisionTrace], None]) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:  # pragma: no cover - listener not registered
            pass

    def _notify_listeners(self, trace: DecisionTrace) -> None:
        for listener in list(self._listeners):
            listener(trace)


_GLOBAL_SCHEDULER = Scheduler()


def get_executor(mode: str = "auto", **hints: Any) -> Executor:
    return _GLOBAL_SCHEDULER.get_executor(mode=mode, **hints)


def configure(config: RuntimeConfig) -> None:
    _GLOBAL_SCHEDULER.configure(config)


def submit(executor: Executor, func: Any, /, *args: Any, **kwargs: Any):
    return async_bridge.submit(executor, func, *args, **kwargs)


def map(
    executor: Executor,
    func: Any,
    iterable: Any,
    /,
    *args: Any,
    timeout: float | None = None,
):
    return async_bridge.map(executor, func, iterable, *args, timeout=timeout)


def reset(*, cancel_futures: bool = False) -> None:
    _GLOBAL_SCHEDULER.reset(cancel_futures=cancel_futures)


def last_decision() -> DecisionTrace | None:
    """Return the most recent decision trace from the global scheduler."""

    return _GLOBAL_SCHEDULER.trace


def lease_executor(
    mode: str = "auto",
    *,
    runtime_config: RuntimeConfig | None = None,
    executor: Executor | None = None,
    max_workers: int | None = None,
    name: str | None = None,
    thread_mode: ThreadMode | None = None,
) -> ExecutorLease:
    """Acquire a managed executor suitable for scoped `Run` usage."""

    return _GLOBAL_SCHEDULER.lease_executor(
        mode=mode,
        runtime_config=runtime_config,
        executor=executor,
        max_workers=max_workers,
        name=name,
        thread_mode=thread_mode,
    )


def add_decision_listener(listener: Callable[[DecisionTrace], None]) -> None:
    """Register a callback invoked whenever the scheduler records a decision."""

    _GLOBAL_SCHEDULER.add_listener(listener)


def remove_decision_listener(listener: Callable[[DecisionTrace], None]) -> None:
    """Remove a previously registered decision listener."""

    _GLOBAL_SCHEDULER.remove_listener(listener)


@contextmanager
def observe_decisions(
    *,
    logger: logging.Logger | None = None,
    level: int = logging.INFO,
) -> Iterator[None]:
    """Context manager that logs scheduler decisions during its scope."""

    active_logger = logger or logging.getLogger("unirun.scheduler")

    def _listener(trace: DecisionTrace) -> None:
        active_logger.log(
            level,
            "scheduler resolved=%s thread_mode=%s reason=%s hints=%s",
            trace.resolved_mode,
            trace.thread_mode,
            trace.reason,
            trace.hints,
        )

    add_decision_listener(_listener)
    try:
        yield
    finally:
        remove_decision_listener(_listener)
