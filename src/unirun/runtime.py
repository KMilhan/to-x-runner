from __future__ import annotations

import asyncio
import warnings
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Literal

from .api import map as api_map
from .api import process_executor, run, thread_executor, wrap_future
from .api import reset as api_reset
from .api import submit as api_submit
from .api import to_process as api_to_process
from .api import to_thread as api_to_thread

ExecutorKind = Literal["auto", "cpu", "io", "thread", "process"]


def _resolve_mode(kind: ExecutorKind) -> str:
    if kind == "cpu" or kind == "process":
        return "process"
    if kind == "io" or kind == "thread":
        return "thread"
    return "auto"


def run_sync(
    func: Callable[..., Any],
    *args: Any,
    kind: ExecutorKind = "auto",
    executor: Any | None = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> Any:
    warnings.warn(
        "run_sync is deprecated; call unirun.run instead",
        DeprecationWarning,
        stacklevel=2,
    )
    result = run(
        func,
        *args,
        mode=_resolve_mode(kind),
        executor=executor,
        **kwargs,
    )
    if timeout is not None:
        # The new `run` helper is synchronous; timeout handling belongs with futures.
        warnings.warn(
            "timeout parameter is ignored in the compatibility layer",
            RuntimeWarning,
            stacklevel=2,
        )
    return result


async def to_executor(
    func: Callable[..., Any],
    *args: Any,
    kind: ExecutorKind = "auto",
    executor: Any | None = None,
    **kwargs: Any,
) -> Any:
    warnings.warn(
        "to_executor is deprecated; call unirun.to_thread/to_process instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if executor is not None:
        future = executor.submit(func, *args, **kwargs)
        return await wrap_future(future)
    mode = _resolve_mode(kind)
    if mode == "process":
        return await api_to_process(func, *args, **kwargs)
    return await api_to_thread(func, *args, **kwargs)


def submit(
    func: Callable[..., Any],
    *args: Any,
    kind: ExecutorKind = "auto",
    executor: Any | None = None,
    **kwargs: Any,
):
    warnings.warn(
        "submit is deprecated; call unirun.submit instead",
        DeprecationWarning,
        stacklevel=2,
    )
    if executor is None:
        mode = _resolve_mode(kind)
        executor = process_executor() if mode == "process" else thread_executor()
    return api_submit(executor, func, *args, **kwargs)


async def amap(
    func: Callable[[Any], Any],
    iterable: Iterable[Any],
    *,
    kind: ExecutorKind = "auto",
    executor: Any | None = None,
) -> list[Any]:
    tasks = [to_executor(func, item, kind=kind, executor=executor) for item in iterable]
    return await gather(*tasks)


def map_sync(
    func: Callable[[Any], Any],
    iterable: Iterable[Any],
    *,
    kind: ExecutorKind = "auto",
    executor: Any | None = None,
):
    warnings.warn(
        "map_sync is deprecated; call unirun.map instead",
        DeprecationWarning,
        stacklevel=2,
    )
    exec_obj = executor
    if exec_obj is None:
        mode = _resolve_mode(kind)
        exec_obj = process_executor() if mode == "process" else thread_executor()
    return api_map(exec_obj, func, iterable)


async def gather(*aws: Awaitable[Any]) -> list[Any]:
    if not aws:
        return []
    if hasattr(asyncio, "TaskGroup"):
        results: list[Any] = [None] * len(aws)

        async def _collect(index: int, awaitable: Awaitable[Any]) -> None:
            results[index] = await awaitable

        async with asyncio.TaskGroup():  # type: ignore[attr-defined]
            await asyncio.gather(*[_collect(idx, aw) for idx, aw in enumerate(aws)])
        return results
    return list(await asyncio.gather(*aws))


def reset_state() -> None:
    warnings.warn(
        "reset_state is deprecated; call unirun.reset instead",
        DeprecationWarning,
        stacklevel=2,
    )
    api_reset(cancel_futures=True)
