"""Compat mirror for :mod:`concurrent.futures` backed by unirun."""

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable
from concurrent.futures import (  # noqa: F401 (re-exported names)
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    CancelledError,
    Executor,
    Future,
    TimeoutError,
    as_completed,
    wait,
)
from concurrent.futures import ProcessPoolExecutor as StdProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor as StdThreadPoolExecutor
from typing import Any, TypeVar

from ... import scheduler
from ...scheduler import ExecutorLease
from .. import _core

T = TypeVar("T")

__all__ = [
    "ALL_COMPLETED",
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "CancelledError",
    "Executor",
    "Future",
    "TimeoutError",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "wait",
    "as_completed",
]


def _passthrough() -> bool:
    return _core.should_passthrough()


_MODE_ALIASES = {
    "threads": "thread",
    "processes": "process",
}


def _canonical_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    return _MODE_ALIASES.get(mode, mode)


def _warn_downgrade(
    label: str,
    *,
    reason: str,
    trace: scheduler.DecisionTrace | None,
) -> None:
    """Issue a runtime warning describing a compat downgrade."""

    details = reason
    if trace is not None:
        requested = _canonical_mode(trace.mode) or trace.mode
        resolved = _canonical_mode(trace.resolved_mode) or trace.resolved_mode
        details = f"{reason} (requested={requested}, resolved={resolved})"
    warnings.warn(
        f"{label} downgraded to stdlib behaviour: {details}",
        RuntimeWarning,
        stacklevel=3,
    )


if _passthrough():  # pragma: no cover - passthrough path validated via smoke tests
    ThreadPoolExecutor = StdThreadPoolExecutor  # type: ignore[assignment]
    ProcessPoolExecutor = StdProcessPoolExecutor  # type: ignore[assignment]
else:

    class _BaseCompatExecutor(Executor):
        """Shared plumbing for compat executors."""

        def __init__(self) -> None:
            self._lease: ExecutorLease | None = None
            self._executor: Executor | None = None
            self._owns_executor = False
            self.decision: scheduler.DecisionTrace | None = None

        def submit(
            self,
            fn: Callable[..., T],
            /,
            *args: Any,
            **kwargs: Any,
        ) -> Future[T]:
            if self._executor is None:  # pragma: no cover - defensive
                raise RuntimeError("executor has been shut down")
            return self._executor.submit(fn, *args, **kwargs)

        def map(
            self,
            func: Callable[..., T],
            *iterables: Iterable[Any],
            timeout: float | None = None,
            chunksize: int = 1,
        ) -> Iterable[T]:
            if self._executor is None:  # pragma: no cover - defensive
                raise RuntimeError("executor has been shut down")
            return self._executor.map(
                func,
                *iterables,
                timeout=timeout,
                chunksize=chunksize,
            )

        def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
            if self._executor is None:
                return
            if self._lease is not None and self._lease.owns_executor:
                self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
            elif hasattr(self._executor, "shutdown"):
                self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
            self._executor = None
            self._lease = None

        def __enter__(self) -> _BaseCompatExecutor:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.shutdown(wait=True)

        def _attach_lease(
            self,
            lease: ExecutorLease,
            *,
            label: str,
            expected_modes: tuple[str, ...],
        ) -> None:
            self._lease = lease
            self._executor = lease.executor
            self._owns_executor = lease.owns_executor
            self.decision = lease.trace
            self._warn_if_fallback(label=label, expected_modes=expected_modes)

        def _warn_if_fallback(
            self,
            *,
            label: str,
            expected_modes: tuple[str, ...],
        ) -> None:
            trace = self.decision
            if trace is None:
                return
            resolved = _canonical_mode(trace.resolved_mode)
            expected = {_canonical_mode(mode) for mode in expected_modes}
            expected.add(_canonical_mode(trace.mode))
            if resolved not in expected:
                _warn_downgrade(label, reason=trace.reason, trace=trace)
            elif "fallback" in trace.reason or "fell back" in trace.reason:
                _warn_downgrade(label, reason=trace.reason, trace=trace)

    class ThreadPoolExecutor(_BaseCompatExecutor):
        """Managed thread pool compat wrapper."""

        def __init__(
            self,
            max_workers: int | None = None,
            thread_name_prefix: str = "",
            initializer: Callable[..., object] | None = None,
            initargs: tuple[Any, ...] = (),
        ) -> None:
            super().__init__()
            if initializer is not None or initargs:
                # Defer to the stdlib implementation when initializer
                # behavior is required.
                _warn_downgrade(
                    "ThreadPoolExecutor",
                    reason="initializer requires stdlib executor",
                    trace=None,
                )
                self._executor = StdThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=thread_name_prefix,
                    initializer=initializer,
                    initargs=initargs,
                )
                self._owns_executor = True
                self.decision = None
                return

            lease = scheduler.lease_executor(
                mode="threads",
                max_workers=max_workers,
                name=thread_name_prefix or _core.default_thread_name(),
            )
            self._attach_lease(
                lease,
                label="ThreadPoolExecutor",
                expected_modes=("thread", "threads"),
            )

    class ProcessPoolExecutor(_BaseCompatExecutor):
        """Managed process pool compat wrapper."""

        def __init__(
            self,
            max_workers: int | None = None,
            mp_context: Any | None = None,
            initializer: Callable[..., object] | None = None,
            initargs: tuple[Any, ...] = (),
        ) -> None:
            super().__init__()
            if mp_context is not None or initializer is not None or initargs:
                _warn_downgrade(
                    "ProcessPoolExecutor",
                    reason="mp_context or initializer requires stdlib executor",
                    trace=None,
                )
                self._executor = StdProcessPoolExecutor(
                    max_workers=max_workers,
                    mp_context=mp_context,
                    initializer=initializer,
                    initargs=initargs,
                )
                self._owns_executor = True
                self.decision = None
                return

            lease = scheduler.lease_executor(
                mode="processes",
                max_workers=max_workers,
            )
            self._attach_lease(
                lease,
                label="ProcessPoolExecutor",
                expected_modes=("process", "processes"),
            )
