from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Executor
from contextvars import ContextVar
from typing import Literal, cast

from .config import RuntimeConfig, ThreadMode
from .scheduler import DecisionTrace, ExecutorLease, lease_executor

RunFlavor = Literal["auto", "threads", "processes", "interpreters", "none"]

_FLAVOR_TO_MODE = {
    "auto": "auto",
    "threads": "thread",
    "processes": "process",
    "interpreters": "subinterpreter",
    "none": "none",
}


class Run:
    """Scoped executor manager for synchronous or asynchronous code blocks."""

    def __init__(
        self,
        *,
        flavor: RunFlavor = "auto",
        executor: Executor | None = None,
        max_workers: int | None = None,
        name: str | None = None,
        config: RuntimeConfig | None = None,
        trace: DecisionTrace | Callable[[DecisionTrace], None] | bool | None = None,
    ) -> None:
        if flavor not in _FLAVOR_TO_MODE:
            valid = ", ".join(sorted(_FLAVOR_TO_MODE))
            message = f"invalid flavor '{flavor}'. Expected one of: {valid}"
            raise ValueError(message)

        self._flavor: RunFlavor = flavor
        self._mode: str = _FLAVOR_TO_MODE[flavor]
        self._provided_executor = executor
        self._max_workers = max_workers
        self._name = name
        self._config = config
        self._trace_request = trace
        self._trace_sink: DecisionTrace | None = None
        self._trace_listener: Callable[[DecisionTrace], None] | None = None
        self._capture_trace = False
        if isinstance(trace, DecisionTrace):
            self._trace_sink = trace
            self._capture_trace = True
        elif isinstance(trace, bool):
            self._capture_trace = trace
        elif callable(trace):
            self._trace_listener = trace
            self._capture_trace = True
        self.trace: DecisionTrace | None = None

        self._entered = False
        self._token = None
        self._lease: ExecutorLease | None = None
        self._executor: Executor | None = None
        self._owns_executor = False
        self._resolved_mode: str | None = None

    def __enter__(self) -> Executor:
        return self._enter()

    async def __aenter__(self) -> Executor:
        return self._enter()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._exit()
        return False

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._exit()
        return False

    # ------------------------------------------------------------------

    def _enter(self) -> Executor:
        if self._entered:
            raise RuntimeError("Run context cannot be entered multiple times")
        self._entered = True

        if self._provided_executor is not None:
            lease = lease_executor(
                mode=self._mode,
                executor=self._provided_executor,
                runtime_config=self._config,
                max_workers=self._max_workers,
                name=self._name,
            )
            self._executor = lease.executor
            self._lease = lease
            self._owns_executor = False
            self._resolved_mode = lease.trace.resolved_mode
            self._record_trace(lease.trace)
        else:
            reusable = self._find_reusable_parent()
            if reusable is not None:
                self._lease = reusable._lease
                self._executor = reusable._executor
                self._owns_executor = False
                self._resolved_mode = reusable._resolved_mode
                self._record_trace(reusable.trace)
            else:
                lease = lease_executor(
                    mode=self._mode,
                    runtime_config=self._config,
                    max_workers=self._max_workers,
                    name=self._name,
                    thread_mode=self._thread_mode_override,
                )
                self._lease = lease
                self._executor = lease.executor
                self._owns_executor = lease.owns_executor
                self._resolved_mode = lease.trace.resolved_mode
                self._record_trace(lease.trace)

        stack = _ACTIVE_RUN_STACK.get()
        self._token = _ACTIVE_RUN_STACK.set(stack + (self,))
        return self._executor  # type: ignore[return-value]

    def _exit(self) -> None:
        if not self._entered:
            return
        try:
            if self._token is not None:
                try:
                    _ACTIVE_RUN_STACK.reset(self._token)
                except ValueError:
                    # Stack mutated unexpectedly; fall back to manual removal.
                    stack = tuple(
                        item for item in _ACTIVE_RUN_STACK.get() if item is not self
                    )
                    _ACTIVE_RUN_STACK.set(stack)
        finally:
            self._entered = False

        if (
            self._owns_executor
            and self._lease is not None
            and self._lease.owns_executor
        ):
            executor = self._lease.executor
            executor.shutdown(wait=True)

    # ------------------------------------------------------------------

    def _find_reusable_parent(self) -> Run | None:
        stack = _ACTIVE_RUN_STACK.get()
        if not stack or self._provided_executor is not None:
            return None
        overrides = self._has_overrides
        for existing in reversed(stack):
            if not existing._owns_executor:
                continue
            if existing._resolved_mode is None:
                continue
            if overrides:
                return None
            if self._mode == "auto" or self._mode == existing._mode:
                return existing
        return None

    @property
    def _has_overrides(self) -> bool:
        return any(
            value is not None
            for value in (self._max_workers, self._name, self._config)
        )

    @property
    def _thread_mode_override(self) -> ThreadMode | None:
        if self._config is not None:
            return self._config.thread_mode
        return None

    def _record_trace(self, trace: DecisionTrace | None) -> None:
        if not trace:
            return
        capture = self._capture_trace or isinstance(self._trace_request, DecisionTrace)
        capture = capture or self._trace_listener is not None
        if not capture:
            return
        self.trace = trace
        if self._trace_sink is not None:
            self._trace_sink.mode = trace.mode
            self._trace_sink.hints = dict(trace.hints)
            self._trace_sink.resolved_mode = trace.resolved_mode
            self._trace_sink.reason = trace.reason
            self._trace_sink.thread_mode = trace.thread_mode
            self._trace_sink.name = trace.name
            self._trace_sink.max_workers = trace.max_workers
        if self._trace_listener is not None:
            self._trace_listener(trace)

    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - convenience
        base = f"Run(flavor={self._flavor!r}"
        if self._name:
            base += f", name={self._name!r}"
        if self._max_workers is not None:
            base += f", max_workers={self._max_workers}"
        return base + ")"


_EMPTY_RUN_STACK = cast(tuple[Run, ...], ())
_ACTIVE_RUN_STACK: ContextVar[tuple[Run, ...]] = ContextVar(
    "unirun_run_stack", default=_EMPTY_RUN_STACK
)


__all__ = ["Run", "RunFlavor"]
