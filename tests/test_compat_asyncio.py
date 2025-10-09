from __future__ import annotations

import asyncio

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
