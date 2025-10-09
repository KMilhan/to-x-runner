from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from ..config import RuntimeConfig

CompatMode = Literal["managed", "passthrough"]


@dataclass(slots=True)
class CompatSettings:
    mode: CompatMode


def load_settings() -> CompatSettings:
    value = os.environ.get("UNIRUN_COMPAT_MODE", "managed").strip().lower()
    if value in {"std", "stdlib", "pass", "passthrough"}:
        return CompatSettings(mode="passthrough")
    return CompatSettings(mode="managed")


SETTINGS = load_settings()


def should_passthrough() -> bool:
    return SETTINGS.mode == "passthrough"


def default_thread_name() -> str | None:
    config = RuntimeConfig.from_env()
    if config.thread_mode == "nogil":
        return "unirun-compat-thread-nogil"
    if config.thread_mode == "gil":
        return "unirun-compat-thread-gil"
    return "unirun-compat-thread"
