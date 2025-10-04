from __future__ import annotations

import multiprocessing
import sys

import pytest

from unirun import process_executor
from unirun.executors.process import (
    _DEFAULT_CONTEXT,
    get_process_pool,
    reset_process_pool,
)


def test_process_executor_returns_singleton() -> None:
    first = process_executor()
    second = process_executor()
    assert first is second


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process pool hint test skipped on Windows",
)
def test_process_executor_respects_max_workers_hint() -> None:
    baseline = process_executor(max_workers=1)
    updated = process_executor(max_workers=2)
    assert baseline is not updated
    assert getattr(updated, "_max_workers", None) == 2


@pytest.mark.skipif(
    len(multiprocessing.get_all_start_methods()) < 2,
    reason="no alternate start method available",
)
def test_process_executor_resets_on_context_change() -> None:
    reset_process_pool()
    first = get_process_pool(max_workers=1)
    methods = [
        method
        for method in multiprocessing.get_all_start_methods()
        if method != _DEFAULT_CONTEXT
    ]
    if not methods:
        pytest.skip("no alternate start method available")  # pragma: no cover
    try:
        second = get_process_pool(max_workers=1, mp_context=methods[0])
    except ValueError:  # pragma: no cover
        pytest.skip("alternate start method unsupported")  # pragma: no cover
    assert second is not first
    reset_process_pool()
