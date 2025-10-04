from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ExecutorMode = Literal["auto", "thread", "process", "subinterpreter", "none"]


@dataclass(slots=True)
class RuntimeConfig:
    """User-tunable settings that influence how executors are selected.

    The defaults keep automation enabled while still allowing call sites to pin
    behavior when predictability beats heuristics.
    """

    mode: ExecutorMode = "auto"
    cpu_bound: bool | None = None
    io_bound: bool | None = None
    prefers_subinterpreters: bool | None = None
    max_workers: int | None = None
    auto: bool = True

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        """Load overrides from environment variables.

        Supported variables (all optional):

        ``UNIRUN_MODE``
            One of ``auto``, ``thread``, ``process``, ``subinterpreter``, ``none``.
        ``UNIRUN_AUTO``
            Boolean flag (``1``/``true``/``yes``) controlling whether heuristics run.
        ``UNIRUN_CPU_BOUND`` / ``UNIRUN_IO_BOUND``
            Boolean hints applied globally when heuristics are enabled.
        ``UNIRUN_PREFERS_SUBINTERPRETERS``
            Boolean hint signalling that sub-interpreters should be considered first.
        ``UNIRUN_MAX_WORKERS``
            Integer limiting thread/process pool sizes chosen automatically.
        """

        def _parse_bool(value: str | None) -> bool | None:
            if value is None:
                return None
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
            return None

        def _parse_int(value: str | None) -> int | None:
            if value is None:
                return None
            try:
                parsed = int(value)
            except ValueError:
                return None
            return parsed if parsed >= 0 else None

        env = os.environ

        mode_raw = env.get("UNIRUN_MODE", "auto").strip().lower()
        mode: ExecutorMode
        if mode_raw in {"auto", "thread", "process", "subinterpreter", "none"}:
            mode = mode_raw  # type: ignore[assignment]
        else:
            mode = "auto"

        auto_flag = _parse_bool(env.get("UNIRUN_AUTO"))
        cpu_hint = _parse_bool(env.get("UNIRUN_CPU_BOUND"))
        io_hint = _parse_bool(env.get("UNIRUN_IO_BOUND"))
        sub_hint = _parse_bool(env.get("UNIRUN_PREFERS_SUBINTERPRETERS"))
        max_workers = _parse_int(env.get("UNIRUN_MAX_WORKERS"))

        auto = auto_flag if auto_flag is not None else True

        return cls(
            mode=mode,
            cpu_bound=cpu_hint,
            io_bound=io_hint,
            prefers_subinterpreters=sub_hint,
            max_workers=max_workers,
            auto=auto,
        )
