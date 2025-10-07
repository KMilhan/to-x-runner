"""Drop-in replacements for :mod:`concurrent.futures` backed by the scheduler."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import (
    ALL_COMPLETED,
    BrokenExecutor,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    CancelledError,
    Executor,
    Future,
    InvalidStateError,
    ProcessPoolExecutor as _StdProcessPoolExecutor,
    ThreadPoolExecutor as _StdThreadPoolExecutor,
    TimeoutError,
    as_completed as _as_completed,
    wait as _wait,
)
from typing import Any, Tuple, TypeVar

from ..scheduler import ExecutorLease, lease_executor

_T = TypeVar("_T")


def _tupled(value: Iterable[object]) -> Tuple[object, ...]:
    if isinstance(value, tuple):
        return value
    return tuple(value)


def _should_fallback_to_stdlib(**hints: Any) -> bool:
    if hints.get("initializer") is not None:
        return True
    if hints.get("initargs"):
        return True
    if hints.get("mp_context") is not None:
        return True
    return False


class _CompatExecutor(Executor):
    """Wrapper exposing stdlib semantics while delegating to managed executors."""

    _delegate: Executor
    _lease: ExecutorLease | None
    _owns_executor: bool

    def __init__(self, delegate: Executor, lease: ExecutorLease | None) -> None:
        self._delegate = delegate
        self._lease = lease
        self._owns_executor = bool(lease.owns_executor) if lease is not None else True
        self._shutdown = False
        self._max_workers = getattr(delegate, "_max_workers", None)

    def __enter__(self) -> "_CompatExecutor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.shutdown()
        return False

    def submit(self, fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> Future[_T]:
        if self._shutdown:
            raise RuntimeError("cannot schedule new futures after shutdown")
        return self._delegate.submit(fn, *args, **kwargs)

    def map(
        self,
        func: Callable[[Any], _T],
        iterable: Iterable[Any],
        /,
        *iterables: Iterable[Any],
        timeout: float | None = None,
        chunksize: int = 1,
    ) -> Iterator[_T]:
        if self._shutdown:
            raise RuntimeError("cannot schedule new futures after shutdown")
        delegate_map = getattr(self._delegate, "map", None)
        if delegate_map is None:
            return super().map(func, iterable, *iterables, timeout=timeout)
        return delegate_map(func, iterable, *iterables, timeout=timeout, chunksize=chunksize)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        if self._owns_executor and hasattr(self._delegate, "shutdown"):
            self._delegate.shutdown(wait=wait, cancel_futures=cancel_futures)

    @property
    def delegate(self) -> Executor:
        return self._delegate


class ThreadPoolExecutor(_CompatExecutor):
    """Compat-aware :class:`ThreadPoolExecutor` replacement."""

    def __init__(
        self,
        max_workers: int | None = None,
        thread_name_prefix: str = "",
        initializer: Callable[..., object] | None = None,
        initargs: Iterable[object] = (),
    ) -> None:
        materialised_args = _tupled(initargs)
        if _should_fallback_to_stdlib(
            initializer=initializer,
            initargs=materialised_args,
        ):
            delegate = stdlib_thread_pool_executor(
                max_workers=max_workers,
                thread_name_prefix=thread_name_prefix,
                initializer=initializer,
                initargs=materialised_args,
            )
            super().__init__(delegate, None)
            return
        lease = lease_executor(
            mode="thread",
            max_workers=max_workers,
            name=thread_name_prefix or None,
        )
        super().__init__(lease.executor, lease)


class ProcessPoolExecutor(_CompatExecutor):
    """Compat-aware :class:`ProcessPoolExecutor` replacement."""

    def __init__(
        self,
        max_workers: int | None = None,
        mp_context: Any | None = None,
        initializer: Callable[..., object] | None = None,
        initargs: Iterable[object] = (),
    ) -> None:
        materialised_args = _tupled(initargs)
        if _should_fallback_to_stdlib(
            mp_context=mp_context,
            initializer=initializer,
            initargs=materialised_args,
        ):
            delegate = stdlib_process_pool_executor(
                max_workers=max_workers,
                mp_context=mp_context,
                initializer=initializer,
                initargs=materialised_args,
            )
            super().__init__(delegate, None)
            return
        lease = lease_executor(
            mode="process",
            max_workers=max_workers,
        )
        super().__init__(lease.executor, lease)


def as_completed(fs: Iterable[Future[_T]], timeout: float | None = None):
    return _as_completed(fs, timeout=timeout)


def wait(
    fs: Iterable[Future[Any]],
    timeout: float | None = None,
    return_when: str = ALL_COMPLETED,
):
    return _wait(fs, timeout=timeout, return_when=return_when)


__all__ = [
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "Future",
    "CancelledError",
    "TimeoutError",
    "BrokenExecutor",
    "InvalidStateError",
    "as_completed",
    "wait",
    "ALL_COMPLETED",
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "stdlib_thread_pool_executor",
    "stdlib_process_pool_executor",
]


def stdlib_thread_pool_executor(
    max_workers: int | None = None,
    thread_name_prefix: str = "",
    initializer: Callable[..., object] | None = None,
    initargs: Iterable[object] = (),
) -> _StdThreadPoolExecutor:
    return _StdThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix=thread_name_prefix,
        initializer=initializer,
        initargs=_tupled(initargs),
    )


def stdlib_process_pool_executor(
    max_workers: int | None = None,
    mp_context: Any | None = None,
    initializer: Callable[..., object] | None = None,
    initargs: Iterable[object] = (),
) -> _StdProcessPoolExecutor:
    return _StdProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=mp_context,
        initializer=initializer,
        initargs=_tupled(initargs),
    )
