from __future__ import annotations

from concurrent.futures import Executor
from dataclasses import dataclass
from typing import Any

from .capabilities import RuntimeCapabilities, detect_capabilities
from .config import RuntimeConfig
from .executors import async_bridge
from .executors.process import get_process_pool, reset_process_pool
from .executors.subinterpreter import (
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

    def as_dict(self) -> dict[str, Any]:
        """Represent the trace as plain data for logging or testing."""

        return {
            "mode": self.mode,
            "hints": dict(self.hints),
            "resolved_mode": self.resolved_mode,
            "reason": self.reason,
        }


class Scheduler:
    """Co-ordinates executor selection while keeping stdlib semantics."""

    def __init__(self, *, config: RuntimeConfig | None = None) -> None:
        self._config = config or RuntimeConfig.from_env()
        self._capabilities: RuntimeCapabilities = detect_capabilities()
        self._trace: DecisionTrace | None = None

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

        resolved_mode = self._resolve_mode(mode, hints)
        executor = self._executor_for_mode(resolved_mode, hints)
        self._trace = DecisionTrace(
            mode=mode,
            hints=hints,
            resolved_mode=resolved_mode,
            reason=self._reason_for(resolved_mode, hints),
        )
        return executor

    def reset(self, *, cancel_futures: bool = False) -> None:
        reset_thread_pool(cancel_futures=cancel_futures)
        reset_process_pool(cancel_futures=cancel_futures)
        reset_interpreter_executor(cancel_futures=cancel_futures)
        self.refresh_capabilities()
        self._trace = None

    def _resolve_mode(self, mode: str, hints: dict[str, Any]) -> str:
        config = self._config
        if not config.auto:
            return config.mode if config.mode != "auto" else "none"

        if mode == "none":
            return "none"
        if mode != "auto":
            return mode

        if config.mode != "auto":
            return config.mode

        cpu_bound = hints.get("cpu_bound", config.cpu_bound)
        io_bound = hints.get("io_bound", config.io_bound)
        prefer_sub = hints.get(
            "prefers_subinterpreters",
            config.prefers_subinterpreters,
        )

        if prefer_sub and self._capabilities.supports_subinterpreters:
            return "subinterpreter"

        if cpu_bound:
            if (
                not self._capabilities.gil_enabled
                or self._capabilities.free_threading_build
            ):
                return "thread"
            return "process"

        if io_bound:
            return "thread"

        return "thread"

    def _executor_for_mode(self, mode: str, hints: dict[str, Any]) -> Executor:
        if mode == "none":
            return get_thread_pool(max_workers=hints.get("max_workers"))
        if mode == "thread":
            configured_workers = self._config.max_workers
            suggested_workers = self._capabilities.suggested_io_workers
            max_workers = hints.get(
                "max_workers",
                configured_workers or suggested_workers,
            )
            return get_thread_pool(max_workers=max_workers)
        if mode == "process":
            configured_workers = self._config.max_workers
            suggested_workers = self._capabilities.suggested_process_workers
            max_workers = hints.get(
                "max_workers",
                configured_workers or suggested_workers,
            )
            return get_process_pool(max_workers=max_workers)
        if mode == "subinterpreter":
            return get_interpreter_executor(max_workers=hints.get("max_workers"))
        if mode == "provided":  # pragma: no cover - guardrail
            raise RuntimeError("Provided mode is reserved for user-supplied executors")
        # Default to thread pool for safety.
        return get_thread_pool(max_workers=hints.get("max_workers"))

    def _reason_for(self, mode: str, hints: dict[str, Any]) -> str:
        if mode == "process":
            return "cpu-bound hints or GIL-enabled runtime suggested process pool"
        if mode == "thread":
            return "io-bound or free-threaded runtime prefers thread pool"
        if mode == "subinterpreter":
            return "caller requested sub-interpreters and runtime supports them"
        if mode == "none":
            return "automation disabled; defaulting to shared thread pool"
        return "used caller-provided executor"


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
