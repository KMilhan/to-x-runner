from __future__ import annotations

import os
import platform
import sys
import sysconfig
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """Snapshot of concurrency-related runtime features.

    The structure mirrors standard-library concepts so higher layers can stay
    terminology-compatible with `concurrent.futures` and `asyncio`.
    """

    python_version: tuple[int, int, int]
    implementation: str
    gil_enabled: bool
    free_threading_build: bool
    supports_subinterpreters: bool
    cpu_count: int
    suggested_io_workers: int
    suggested_cpu_workers: int
    suggested_process_workers: int

    @property
    def python_release(self) -> str:
        major, minor, micro = self.python_version
        return f"{major}.{minor}.{micro}"


def detect_capabilities() -> RuntimeCapabilities:
    version = sys.version_info
    cpu_count = os.cpu_count() or 1
    supports_free_threading_build = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    gil_enabled = _is_gil_enabled()
    supports_subinterpreters = hasattr(sys, "interpreters")

    suggested_io_workers = max(4, min(32, cpu_count * 5))
    if supports_free_threading_build and not gil_enabled:
        suggested_cpu_workers = cpu_count
        suggested_process_workers = max(1, cpu_count - 1)
    else:
        # For GIL builds prefer processes for CPU-bound work.
        suggested_cpu_workers = max(4, min(32, cpu_count * 5))
        suggested_process_workers = max(1, cpu_count - 1)

    return RuntimeCapabilities(
        python_version=(version.major, version.minor, version.micro),
        implementation=platform.python_implementation(),
        gil_enabled=gil_enabled,
        free_threading_build=supports_free_threading_build,
        supports_subinterpreters=supports_subinterpreters,
        cpu_count=cpu_count,
        suggested_io_workers=suggested_io_workers,
        suggested_cpu_workers=suggested_cpu_workers,
        suggested_process_workers=suggested_process_workers,
    )


def _ensure_gil_checker() -> Callable[[], bool]:
    """Return a callable mirroring ``sys._is_gil_enabled`` semantics."""

    checker = getattr(sys, "_is_gil_enabled", None)
    if checker is not None:
        return checker

    def _fallback_checker() -> bool:
        return True

    sys._is_gil_enabled = _fallback_checker
    return _fallback_checker


def _is_gil_enabled() -> bool:
    checker = _ensure_gil_checker()
    try:
        return bool(checker())
    except RuntimeError:
        # Some implementations may raise if called from a non-main thread.
        return True
