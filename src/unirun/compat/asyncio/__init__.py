"""Compat mirror for :mod:`asyncio` helpers used in unirun migrations."""

from __future__ import annotations

import asyncio as _asyncio
import importlib
import pkgutil
import sys
from collections.abc import Callable
from typing import Any

from ... import Run
from ... import to_thread as unirun_to_thread
from ...compat import _core

__all__ = [
    "CancelledError",
    "Future",
    "Task",
    "TaskGroup",
    "gather",
    "get_event_loop",
    "get_running_loop",
    "new_event_loop",
    "run",
    "run_in_executor",
    "sleep",
    "to_thread",
]

CancelledError = _asyncio.CancelledError
Future = _asyncio.Future
Task = _asyncio.Task
TaskGroup = getattr(_asyncio, "TaskGroup", None)
gather = _asyncio.gather
get_event_loop = _asyncio.get_event_loop
get_running_loop = _asyncio.get_running_loop
new_event_loop = _asyncio.new_event_loop
run = _asyncio.run
sleep = _asyncio.sleep
events = _asyncio.events

if hasattr(_asyncio, "__all__"):
    __all__ = sorted(set(__all__) | set(_asyncio.__all__) | {"events"})
else:  # pragma: no cover - stdlib always defines __all__
    __all__.append("events")


def _bootstrap_stdlib_submodules() -> None:
    prefix = f"{_asyncio.__name__}."
    for _, fullname, _ in pkgutil.walk_packages(_asyncio.__path__, prefix=prefix):
        try:
            module = importlib.import_module(fullname)
        except ImportError:  # pragma: no cover - platform-specific modules
            continue
        sys.modules.setdefault(fullname, module)
        short_name = fullname.removeprefix(prefix)
        top_level, _, _ = short_name.partition(".")
        if top_level and not hasattr(sys.modules[__name__], top_level):
            setattr(sys.modules[__name__], top_level, module)


_bootstrap_stdlib_submodules()


if _core.should_passthrough():  # pragma: no cover - passthrough validated elsewhere
    to_thread = _asyncio.to_thread  # type: ignore[assignment]

    async def run_in_executor(
        executor: Any,
        func: Callable[..., Any],
        /,
        *args: Any,
    ) -> Any:
        loop = _asyncio.get_running_loop()
        return await loop.run_in_executor(executor, func, *args)

else:

    async def to_thread(
        func: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return await unirun_to_thread(func, *args, **kwargs)

    async def run_in_executor(
        executor: Any | None,
        func: Callable[..., Any],
        /,
        *args: Any,
    ) -> Any:
        loop = _asyncio.get_running_loop()
        if executor is None:
            with Run(flavor="auto") as auto:
                return await loop.run_in_executor(auto, func, *args)
        return await loop.run_in_executor(executor, func, *args)


def __getattr__(name: str) -> Any:
    return getattr(_asyncio, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_asyncio)))
