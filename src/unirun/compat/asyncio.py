"""Async helpers that mirror :mod:`asyncio` entry points."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from ..executors import async_bridge

_T = TypeVar("_T")
_P = ParamSpec("_P")


async def to_thread(
    func: Callable[_P, _T],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _T:
    """Delegate to :func:`unirun.executors.async_bridge.to_thread`."""

    return await async_bridge.to_thread(func, *args, **kwargs)


async def to_process(
    func: Callable[_P, _T],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _T:
    """Bridge onto the shared process pool from async code."""

    return await async_bridge.to_process(func, *args, **kwargs)


def wrap_future(
    future: Any,
    *,
    loop: Any | None = None,
) -> Awaitable[Any]:
    """Expose :func:`asyncio.wrap_future` through the compat surface."""

    return async_bridge.wrap_future(future, loop=loop)
