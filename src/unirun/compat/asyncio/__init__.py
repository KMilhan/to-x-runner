"""Compat mirror for :mod:`asyncio` helpers used in unirun migrations."""

from __future__ import annotations

import asyncio as _asyncio
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

try:
    get_event_loop = _asyncio.get_event_loop
except AttributeError:  # pragma: no cover - exercised via fallback test

    def get_event_loop() -> _asyncio.AbstractEventLoop:
        """Mimic the removed ``asyncio.get_event_loop`` helper on 3.14+."""

        try:
            return _asyncio.get_running_loop()
        except RuntimeError:
            policy = _asyncio.get_event_loop_policy()
            try:
                return policy.get_event_loop()
            except RuntimeError:
                loop = policy.new_event_loop()
                set_loop = getattr(policy, "set_event_loop", None)
                if set_loop is not None:
                    set_loop(loop)
                return loop

get_running_loop = _asyncio.get_running_loop
new_event_loop = _asyncio.new_event_loop
run = _asyncio.run
sleep = _asyncio.sleep


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
