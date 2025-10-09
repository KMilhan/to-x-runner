from __future__ import annotations

import pytest

from unirun.compat.asyncio import run_in_executor, to_thread


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
