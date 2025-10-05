from __future__ import annotations

import doctest
import sys

import pytest

import unirun.api


def _mutation_instrumentation_active() -> bool:
    """Detect whether mutmut instrumentation is active in the current process."""

    module = sys.modules.get("mutmut")
    if module is None:
        return False
    config = getattr(module, "config", None)
    if config is None:
        return True
    return bool(getattr(config, "is_running", True))


def test_unirun_api_doctests() -> None:
    if _mutation_instrumentation_active():
        pytest.skip("mutmut instrumentation breaks multiprocessing trampolines")
    failure_count, _ = doctest.testmod(
        unirun.api,
        optionflags=doctest.NORMALIZE_WHITESPACE,
    )
    assert failure_count == 0
