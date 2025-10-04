from __future__ import annotations

import atexit
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from threading import Lock

_PROCESS_POOL: ProcessPoolExecutor | None = None
_LOCK = Lock()
_ATEEXIT_REGISTERED = False
_PROCESS_POOL_MAX_WORKERS: int | None = None
_PROCESS_POOL_CONTEXT: str | None = None

if sys.platform.startswith("win"):  # pragma: no cover - Windows-specific path
    _DEFAULT_CONTEXT = "spawn"
else:
    _DEFAULT_CONTEXT = "fork"


def get_process_pool(
    *, max_workers: int | None = None, mp_context: str | None = None
) -> ProcessPoolExecutor:
    """Return a shared :class:`ProcessPoolExecutor` configured for CPython quirks."""

    global _PROCESS_POOL
    desired_context = mp_context or _DEFAULT_CONTEXT
    should_reset = False

    with _LOCK:
        if _PROCESS_POOL is not None:
            if max_workers is not None and max_workers != _PROCESS_POOL_MAX_WORKERS:
                should_reset = True
            elif mp_context is not None and desired_context != _PROCESS_POOL_CONTEXT:
                should_reset = True

    if should_reset:
        reset_process_pool(cancel_futures=True)

    with _LOCK:
        if _PROCESS_POOL is None:
            ctx = multiprocessing.get_context(desired_context) if desired_context else None
            _PROCESS_POOL = ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx)
            _record_pool_metadata(context=desired_context, pool=_PROCESS_POOL)
            _register_atexit()
        return _PROCESS_POOL


def reset_process_pool(*, cancel_futures: bool = False) -> None:
    """Tear down the shared process pool if created."""

    global _PROCESS_POOL
    with _LOCK:
        if _PROCESS_POOL is not None:
            _PROCESS_POOL.shutdown(wait=True, cancel_futures=cancel_futures)
            _PROCESS_POOL = None
        _clear_pool_metadata()


def _record_pool_metadata(*, context: str, pool: ProcessPoolExecutor) -> None:
    global _PROCESS_POOL_MAX_WORKERS, _PROCESS_POOL_CONTEXT
    _PROCESS_POOL_CONTEXT = context
    try:
        max_workers = pool._max_workers  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - guard for alt executors
        max_workers = None
    _PROCESS_POOL_MAX_WORKERS = max_workers


def _clear_pool_metadata() -> None:
    global _PROCESS_POOL_MAX_WORKERS, _PROCESS_POOL_CONTEXT
    _PROCESS_POOL_MAX_WORKERS = None
    _PROCESS_POOL_CONTEXT = None


def _register_atexit() -> None:
    global _ATEEXIT_REGISTERED
    if _ATEEXIT_REGISTERED:
        return
    atexit.register(reset_process_pool)
    _ATEEXIT_REGISTERED = True
