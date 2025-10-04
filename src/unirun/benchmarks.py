"""Compatibility shims for the optional benchmark helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unirun_bench.engine import BenchmarkRecord, Scenario, format_table, run_suite

__all__ = ["run_suite", "format_table", "BenchmarkRecord", "Scenario"]


def _load() -> Any:
    return import_module("unirun_bench.engine")


def __getattr__(name: str) -> Any:  # pragma: no cover - import indirection
    module = _load()
    try:
        return getattr(module, name)
    except AttributeError as exc:  # pylint: disable=raise-missing-from
        raise AttributeError(name) from exc
