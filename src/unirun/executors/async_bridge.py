from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import Executor, Future
from functools import partial
from typing import Any, ParamSpec, TypeVar

from .process import get_process_pool
from .threading import get_thread_pool

T = TypeVar("T")
InputT = TypeVar("InputT")
P = ParamSpec("P")


async def to_thread(func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Async helper mirroring :func:`asyncio.to_thread` with shared pools."""

    loop = asyncio.get_running_loop()
    executor = get_thread_pool()
    caller = partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, caller)


async def to_process(func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Bridge synchronous work onto the shared process pool from async code."""

    loop = asyncio.get_running_loop()
    executor = get_process_pool()
    return await loop.run_in_executor(executor, partial(func, *args, **kwargs))


def wrap_future(
    future: Future[Any], *, loop: asyncio.AbstractEventLoop | None = None
) -> Awaitable[Any]:
    """Expose :func:`asyncio.wrap_future` behind a consistent import path."""

    return asyncio.wrap_future(future, loop=loop)


def submit(
    executor: Executor,
    func: Callable[P, T],
    /,
    *args: P.args,
    **kwargs: P.kwargs,
) -> Future[T]:
    """Thin wrapper over :meth:`Executor.submit`.

    Having a dedicated helper keeps type-checkers happy when projects want a
    single import location for submission regardless of executor kind.
    """

    return executor.submit(func, *args, **kwargs)


def map(
    executor: Executor,
    func: Callable[[InputT], T],
    iterable: Iterable[InputT],
    /,
    *args: Iterable[InputT],
    timeout: float | None = None,
) -> Iterable[T]:
    """Delegate to :meth:`Executor.map` for a stdlib-style API."""

    return executor.map(func, iterable, *args, timeout=timeout)
