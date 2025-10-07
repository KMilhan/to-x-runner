from __future__ import annotations

import asyncio
from typing import Iterator

import pytest

from unirun import reset
from unirun.compat import asyncio as compat_asyncio


@pytest.fixture(autouse=True)
def reset_scheduler() -> Iterator[None]:
    """Guarantee bridge helpers use fresh executor state each run."""
    reset(cancel_futures=True)
    yield
    reset(cancel_futures=True)


async def _compute(value: int) -> int:
    """Async helper multiplying a value via compat.to_thread."""
    return await compat_asyncio.to_thread(lambda: value * 2)


def test_to_thread_matches_asyncio_contract() -> None:
    """Compat to_thread should mirror asyncio.to_thread semantics."""
    result = asyncio.run(_compute(6))
    assert result == 12


def test_wrap_future_round_trips_sync_future() -> None:
    """Ensure wrap_future hands async control back to the loop."""
    loop = asyncio.new_event_loop()
    try:
        future = loop.run_in_executor(None, lambda: 5)
        wrapped = compat_asyncio.wrap_future(future, loop=loop)
        result = loop.run_until_complete(wrapped)
        assert result == 5
    finally:
        loop.close()
