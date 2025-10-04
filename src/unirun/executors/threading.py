from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

_THREAD_POOL: ThreadPoolExecutor | None = None
_LOCK = Lock()
_DEFAULT_PREFIX = "unirun-thread"
_ATEEXIT_REGISTERED = False
_THREAD_POOL_MAX_WORKERS: int | None = None
_THREAD_POOL_PREFIX: str = _DEFAULT_PREFIX


def get_thread_pool(
    *, max_workers: int | None = None, thread_name_prefix: str | None = None
) -> ThreadPoolExecutor:
    """Return a process-wide shared :class:`ThreadPoolExecutor`.

    The helper mirrors the stdlib factory while letting the scheduler control
    worker sizing. Callers should treat the returned executor exactly like a
    normal `ThreadPoolExecutor`.
    """

    global _THREAD_POOL
    desired_prefix = thread_name_prefix or _DEFAULT_PREFIX
    should_reset = False

    with _LOCK:
        if _THREAD_POOL is not None:
            if max_workers is not None and max_workers != _THREAD_POOL_MAX_WORKERS:
                should_reset = True
            elif (
                thread_name_prefix is not None
                and desired_prefix != _THREAD_POOL_PREFIX
            ):
                should_reset = True

    if should_reset:
        reset_thread_pool(cancel_futures=True)

    with _LOCK:
        if _THREAD_POOL is None:
            _THREAD_POOL = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=desired_prefix,
            )
            _record_pool_metadata(thread_name_prefix=desired_prefix, pool=_THREAD_POOL)
            _register_atexit()
        return _THREAD_POOL


def reset_thread_pool(*, cancel_futures: bool = False) -> None:
    """Tear down the shared thread pool if it has been created."""

    global _THREAD_POOL
    with _LOCK:
        if _THREAD_POOL is not None:
            _THREAD_POOL.shutdown(wait=True, cancel_futures=cancel_futures)
            _THREAD_POOL = None
        _clear_pool_metadata()


def _record_pool_metadata(*, thread_name_prefix: str, pool: ThreadPoolExecutor) -> None:
    global _THREAD_POOL_MAX_WORKERS, _THREAD_POOL_PREFIX
    _THREAD_POOL_PREFIX = thread_name_prefix
    try:
        max_workers = pool._max_workers  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - guard for alternative executors
        max_workers = None
    _THREAD_POOL_MAX_WORKERS = max_workers


def _clear_pool_metadata() -> None:
    global _THREAD_POOL_MAX_WORKERS, _THREAD_POOL_PREFIX
    _THREAD_POOL_MAX_WORKERS = None
    _THREAD_POOL_PREFIX = _DEFAULT_PREFIX


def _register_atexit() -> None:
    global _ATEEXIT_REGISTERED
    if _ATEEXIT_REGISTERED:
        return
    atexit.register(reset_thread_pool)
    _ATEEXIT_REGISTERED = True
