"""Compat layer mirroring stdlib concurrency entry points."""

from .futures import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    FIRST_EXCEPTION,
    BrokenExecutor,
    CancelledError,
    Future,
    InvalidStateError,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    TimeoutError,
    as_completed,
    stdlib_process_pool_executor,
    stdlib_thread_pool_executor,
    wait,
)
from .asyncio import to_process, to_thread, wrap_future

__all__ = [
    "Future",
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "CancelledError",
    "BrokenExecutor",
    "InvalidStateError",
    "as_completed",
    "wait",
    "ALL_COMPLETED",
    "FIRST_COMPLETED",
    "FIRST_EXCEPTION",
    "TimeoutError",
    "stdlib_thread_pool_executor",
    "stdlib_process_pool_executor",
    "to_thread",
    "to_process",
    "wrap_future",
]
