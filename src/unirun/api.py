from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable
from concurrent.futures import Executor, Future
from typing import Any, ParamSpec, TypeVar

from . import scheduler
from .config import RuntimeConfig
from .executors import async_bridge
from .executors.process import get_process_pool
from .executors.subinterpreter import get_interpreter_executor
from .executors.threading import get_thread_pool
from .scheduler import DecisionTrace

T = TypeVar("T")
InputT = TypeVar("InputT")
P = ParamSpec("P")


def run(
    func: Callable[P, T],
    /,
    *args: P.args,
    mode: str = "auto",
    executor: Executor | None = None,
    cpu_bound: bool | None = None,
    io_bound: bool | None = None,
    prefers_subinterpreters: bool | None = None,
    max_workers: int | None = None,
    **kwargs: P.kwargs,
) -> T:
    warnings.warn(
        "unirun.run is deprecated; use the Run context manager instead",
        DeprecationWarning,
        stacklevel=2,
    )
    """Execute *func* synchronously (deprecated).

    This helper remains for backwards compatibility. New code should prefer::

        from unirun import Run

        with Run(flavor="threads") as executor:
            executor.submit(func, *args, **kwargs).result()
    """

    hints: dict[str, Any] = {
        "executor": executor,
        "cpu_bound": cpu_bound,
        "io_bound": io_bound,
        "prefers_subinterpreters": prefers_subinterpreters,
        "max_workers": max_workers,
    }
    # Remove ``None`` entries so the scheduler can fall back to defaults.
    filtered_hints = {key: value for key, value in hints.items() if value is not None}
    exec_obj = scheduler.get_executor(mode=mode, **filtered_hints)
    future = scheduler.submit(exec_obj, func, *args, **kwargs)
    return future.result()


def thread_executor(*, max_workers: int | None = None) -> Executor:
    """Expose the shared thread pool as a standard :class:`Executor`.

    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import reset
    >>> executor = thread_executor(max_workers=1)
    >>> future = executor.submit(lambda: "hello")
    >>> future.result()
    'hello'
    >>> with ThreadPoolExecutor(max_workers=1) as pool:
    ...     pool.submit(lambda: "hello").result()
    'hello'
    >>> reset()
    """

    return get_thread_pool(max_workers=max_workers)


def process_executor(*, max_workers: int | None = None) -> Executor:
    """Expose the shared process pool.

    >>> import math, sys
    >>> from unirun import reset
    >>> if sys.platform != "win32":
    ...     executor = process_executor(max_workers=1)
    ...     executor.submit(math.sqrt, 9).result()
    3.0
    >>> if sys.platform != "win32":
    ...     from concurrent.futures import ProcessPoolExecutor
    ...     with ProcessPoolExecutor(max_workers=1) as pool:
    ...         pool.submit(math.sqrt, 9).result()
    3.0
    >>> reset()
    """

    return get_process_pool(max_workers=max_workers)


def interpreter_executor(
    *, max_workers: int | None = None, isolated: bool = True
) -> Executor:
    """Return an executor backed by sub-interpreters (falls back to threads).

    >>> from unirun import reset
    >>> from unirun.workloads import simulate_blocking_io
    >>> executor = interpreter_executor()
    >>> future = executor.submit(simulate_blocking_io, 0.0)
    >>> future.result()
    0.0
    >>> reset()
    """

    return get_interpreter_executor(max_workers=max_workers, isolated=isolated)


def get_executor(mode: str = "auto", **hints: Any) -> Executor:
    """Delegate to the global scheduler for convenience.

    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import reset
    >>> executor = get_executor(mode="thread")
    >>> executor.submit(lambda: 4 + 4).result()
    8
    >>> with ThreadPoolExecutor() as pool:
    ...     pool.submit(lambda: 4 + 4).result()
    8
    >>> reset()
    """

    return scheduler.get_executor(mode=mode, **hints)


def submit(
    executor: Executor, func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
) -> Future[T]:
    """Submit *func* to *executor* mirroring :meth:`Executor.submit`.

    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import reset, thread_executor
    >>> executor = thread_executor()
    >>> submit(executor, pow, 2, 5).result()
    32
    >>> with ThreadPoolExecutor() as pool:
    ...     pool.submit(pow, 2, 5).result()
    32
    >>> reset()
    """

    return scheduler.submit(executor, func, *args, **kwargs)


def map(
    executor: Executor,
    func: Callable[[InputT], T],
    iterable: Iterable[InputT],
    /,
    *iterables: Iterable[InputT],
    timeout: float | None = None,
) -> Iterable[T]:
    """Apply *func* across *iterable* using the provided executor.

    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import reset, thread_executor
    >>> executor = thread_executor()
    >>> list(map(executor, str.upper, ["a", "b"]))
    ['A', 'B']
    >>> with ThreadPoolExecutor() as pool:
    ...     list(pool.map(str.upper, ["a", "b"]))
    ['A', 'B']
    >>> reset()
    """

    return scheduler.map(executor, func, iterable, *iterables, timeout=timeout)


async def to_thread(func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Run ``func`` in the shared thread pool while awaiting the result.

    >>> import asyncio
    >>> async def stdlib() -> str:
    ...     return await asyncio.to_thread(lambda: "done")
    >>> async def main() -> str:
    ...     return await to_thread(lambda: "done")
    >>> asyncio.run(stdlib())
    'done'
    >>> asyncio.run(main())
    'done'
    """

    return await async_bridge.to_thread(func, *args, **kwargs)


async def to_process(func: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """Await ``func`` executed in the shared process pool.

    >>> import asyncio, math, sys
    >>> async def stdlib() -> float:
    ...     loop = asyncio.get_running_loop()
    ...     return await loop.run_in_executor(None, math.sqrt, 16)
    >>> async def main() -> float:
    ...     return await to_process(math.sqrt, 16)
    >>> if sys.platform != "win32":
    ...     asyncio.run(stdlib())
    4.0
    >>> if sys.platform != "win32":
    ...     asyncio.run(main())
    4.0
    >>> reset()
    """

    return await async_bridge.to_process(func, *args, **kwargs)


def wrap_future(*args: Any, **kwargs: Any) -> Any:
    """Expose :func:`asyncio.wrap_future` under the `unirun` namespace.

    >>> import asyncio
    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import reset, thread_executor
    >>> executor = thread_executor()
    >>> future = executor.submit(lambda: "value")
    >>> async def stdlib() -> str:
    ...     with ThreadPoolExecutor() as pool:
    ...         fut = pool.submit(lambda: "value")
    ...         return await asyncio.wrap_future(fut)
    >>> async def main() -> str:
    ...     return await wrap_future(future)
    >>> asyncio.run(stdlib())
    'value'
    >>> asyncio.run(main())
    'value'
    >>> reset()
    """

    return async_bridge.wrap_future(*args, **kwargs)


def reset(*, cancel_futures: bool = False) -> None:
    """Tear down the shared executors and clear cached capabilities.

    Use this helper in tests or long-lived processes when you need to ensure
    pools are recreated with fresh configuration.

    >>> reset()
    """

    scheduler.reset(cancel_futures=cancel_futures)


def configure(config: RuntimeConfig) -> None:
    """Replace the global scheduler configuration.

    >>> from unirun import RuntimeConfig
    >>> from concurrent.futures import ThreadPoolExecutor
    >>> configure(RuntimeConfig(mode="thread", auto=False))
    >>> executor = get_executor()
    >>> executor is thread_executor()
    True
    >>> with ThreadPoolExecutor() as pool:
    ...     isinstance(pool, ThreadPoolExecutor)
    True
    >>> configure(RuntimeConfig())
    >>> reset()
    """

    scheduler.configure(config)


def last_decision() -> DecisionTrace | None:
    """Expose the last scheduler decision for observability.

    >>> from concurrent.futures import ThreadPoolExecutor
    >>> from unirun import Run
    >>> scope = Run(flavor="threads", trace=True)
    >>> with scope:
    ...     pass
    >>> isinstance(last_decision(), DecisionTrace)
    True
    >>> with ThreadPoolExecutor() as pool:
    ...     pool.submit(lambda: 1).result()
    1
    >>> reset()
    """

    return scheduler.last_decision()
