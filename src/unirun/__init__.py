"""stdlib-aligned execution helpers for Python's evolving runtimes.

`unirun` exposes helpers that mirror the `concurrent.futures`, `asyncio`, and
`multiprocessing` vocabulary so teams can adopt new interpreter capabilities
without rewriting call sites. The implementation intentionally stays thin here;
see individual modules for details.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from . import compat
from .api import (
    configure,
    get_executor,
    interpreter_executor,
    last_decision,
    map,
    process_executor,
    reset,
    run,
    submit,
    thread_executor,
    to_process,
    to_thread,
    wrap_future,
)
from .capabilities import RuntimeCapabilities, detect_capabilities
from .config import RuntimeConfig
from .run import Run, RunFlavor
from .scheduler import (
    DecisionTrace,
    add_decision_listener,
    observe_decisions,
    remove_decision_listener,
)

__all__ = [
    "RuntimeCapabilities",
    "RuntimeConfig",
    "Run",
    "RunFlavor",
    "DecisionTrace",
    "add_decision_listener",
    "remove_decision_listener",
    "observe_decisions",
    "configure",
    "detect_capabilities",
    "get_executor",
    "interpreter_executor",
    "last_decision",
    "map",
    "process_executor",
    "reset",
    "run",
    "submit",
    "thread_executor",
    "to_process",
    "to_thread",
    "wrap_future",
    "compat",
]

try:
    __version__ = version("unirun")
except PackageNotFoundError:  # pragma: no cover - during local dev
    __version__ = "0.0.0"
