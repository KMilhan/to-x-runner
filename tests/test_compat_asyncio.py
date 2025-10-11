from __future__ import annotations

import asyncio
import importlib
import sys

import pytest

from unirun.compat.asyncio import TaskGroup, gather, run_in_executor, to_thread


@pytest.mark.asyncio
async def test_to_thread_executes_function() -> None:
    result = await to_thread(lambda value: value + 1, 41)
    assert result == 42


@pytest.mark.asyncio
async def test_run_in_executor_uses_auto_executor() -> None:
    result = await run_in_executor(None, lambda value: value + 1, 41)
    assert result == 42


@pytest.mark.asyncio
async def test_run_in_executor_respects_custom_executor() -> None:
    from unirun.compat.concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        result = await run_in_executor(executor, lambda value: value + 2, 40)
    assert result == 42


@pytest.mark.asyncio
@pytest.mark.skipif(TaskGroup is None, reason="TaskGroup not available")
async def test_taskgroup_with_to_thread() -> None:
    results: list[int] = []

    async def worker(value: int) -> None:
        result = await to_thread(lambda x: x + 1, value)
        results.append(result)

    async with TaskGroup() as group:  # type: ignore[func-returns-value]
        for item in range(3):
            group.create_task(worker(item))

    assert sorted(results) == [1, 2, 3]


def test_gather_and_taskgroup_identity() -> None:
    assert gather is asyncio.gather
    if TaskGroup is not None:
        assert hasattr(asyncio, "TaskGroup")
        assert TaskGroup is asyncio.TaskGroup  # type: ignore[attr-defined]


def test_get_event_loop_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "unirun.compat.asyncio"
    original_module = sys.modules.pop(module_name, None)

    with monkeypatch.context() as patch:
        patch.delattr(asyncio, "get_event_loop", raising=False)
        compat_asyncio = importlib.import_module(module_name)
        loop = compat_asyncio.get_event_loop()
        try:
            assert isinstance(loop, asyncio.AbstractEventLoop)
        finally:
            loop.close()
            policy = asyncio.get_event_loop_policy()
            set_loop = getattr(policy, "set_event_loop", None)
            if set_loop is not None:
                try:
                    set_loop(None)
                except Exception:
                    pass
    sys.modules.pop(module_name, None)
    if original_module is not None:
        sys.modules[module_name] = original_module
        importlib.reload(original_module)
    else:
        importlib.import_module(module_name)
