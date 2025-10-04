from __future__ import annotations

"""Compatibility shims for the optional benchmark helpers.

The real implementation lives in ``unirun_bench.engine`` so that importing the
core ``unirun`` package does not eagerly pull in the benchmark machinery. The
functions defined here re-export that implementation on demand.
"""

from importlib import import_module
from typing import Any

__all__ = ["run_suite", "format_table", "BenchmarkRecord", "Scenario"]


def _load() -> Any:
    return import_module("unirun_bench.engine")


def __getattr__(name: str) -> Any:  # pragma: no cover - exercised indirectly via imports
    module = _load()
    try:
        return getattr(module, name)
    except AttributeError as exc:  # pylint: disable=raise-missing-from
        raise AttributeError(name) from exc
