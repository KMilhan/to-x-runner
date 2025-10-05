"""Runnable concurrency examples that showcase unirun helpers.

Refer to ``examples/README.md`` for the full scenario catalog. Each module
exposes a ``SCENARIOS`` list and a ``run_all()`` helper so you can render
structured demonstrations without wiring additional infrastructure.
"""

from __future__ import annotations

from . import cpu_bound, io_bound, mixed_pipelines

__all__ = [
    "io_bound",
    "cpu_bound",
    "mixed_pipelines",
]
