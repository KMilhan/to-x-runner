"""Compat mirror for :mod:`concurrent.futures` backed by unirun."""

from __future__ import annotations

import itertools
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import (  # noqa: F401 (re-exported names)
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    BrokenExecutor,
    CancelledError,
    Executor,
    Future,
    InvalidStateError,
    TimeoutError,
    as_completed,
    wait,
)
from concurrent.futures import ProcessPoolExecutor as StdProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor as StdThreadPoolExecutor
import concurrent.futures.process as _stdlib_process
from typing import Any, TypeVar

from ... import scheduler
from ...scheduler import ExecutorLease
from .. import _core

T = TypeVar("T")

__all__ = [
    "ALL_COMPLETED",
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "BrokenExecutor",
    "CancelledError",
    "Executor",
    "Future",
    "InvalidStateError",
    "TimeoutError",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "wait",
    "as_completed",
]

process = _stdlib_process
sys.modules.setdefault("concurrent.futures.process", process)
_THREAD_EXECUTOR_COUNTER = itertools.count()


def _passthrough() -> bool:
    return _core.should_passthrough()


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
            self._proxy_attrs: dict[str, Any] = {}

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
            for name in ("_threads", "_processes"):
                if hasattr(self._executor, name):
                    self._proxy_attrs[name] = getattr(self._executor, name)
            self._executor = None
            self._lease = None

        def __enter__(self) -> _BaseCompatExecutor:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.shutdown(wait=True)

        def _attach_lease(self, lease: ExecutorLease) -> None:
            self._lease = lease
            self._executor = lease.executor
            self._owns_executor = lease.owns_executor
            self.decision = lease.trace
            self._proxy_attrs.clear()

        def __getattr__(self, name: str) -> Any:
            executor = self._executor
            if executor is None:
                if name in self._proxy_attrs:
                    return self._proxy_attrs[name]
                raise AttributeError(name)
            return getattr(executor, name)

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
            prefix = thread_name_prefix or f"ThreadPoolExecutor-{next(_THREAD_EXECUTOR_COUNTER)}"
            if initializer is not None or initargs:
                # Defer to the stdlib implementation when initializer
                # behavior is required.
                self._executor = StdThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=prefix,
                    initializer=initializer,
                    initargs=initargs,
                )
                self._owns_executor = True
                self.decision = None
                self._proxy_attrs.clear()
                return

            lease = scheduler.lease_executor(
                mode="threads",
                max_workers=max_workers,
                name=prefix,
            )
            self._attach_lease(lease)

    class ProcessPoolExecutor(_BaseCompatExecutor):
        """Managed process pool compat wrapper."""

        def __init__(
            self,
            max_workers: int | None = None,
            mp_context: Any | None = None,
            initializer: Callable[..., object] | None = None,
            initargs: tuple[Any, ...] = (),
            *,
            max_tasks_per_child: int | None = None,
        ) -> None:
            super().__init__()
            if (
                mp_context is not None
                or initializer is not None
                or initargs
                or max_tasks_per_child is not None
            ):
                self._executor = StdProcessPoolExecutor(
                    max_workers=max_workers,
                    mp_context=mp_context,
                    initializer=initializer,
                    initargs=initargs,
                    max_tasks_per_child=max_tasks_per_child,
                )
                self._owns_executor = True
                self.decision = None
                return

            lease = scheduler.lease_executor(
                mode="processes",
                max_workers=max_workers,
            )
            self._attach_lease(lease)
