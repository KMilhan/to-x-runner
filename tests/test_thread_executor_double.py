from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from unirun import thread_executor


def test_thread_map_matches_stdlib() -> None:
    data = [1, 2, 3]
    executor = thread_executor()
    results = list(executor.map(lambda value: value * 2, data))
    with ThreadPoolExecutor() as pool:
        expected = list(pool.map(lambda value: value * 2, data))
    assert results == expected
