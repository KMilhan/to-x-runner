from __future__ import annotations

import os
from unittest import mock

from unirun import RuntimeConfig


def test_runtime_config_defaults() -> None:
    config = RuntimeConfig()
    assert config.mode == "auto"
    assert config.auto is True


def test_runtime_config_from_env() -> None:
    with mock.patch.dict(
        os.environ,
        {
            "UNIRUN_MODE": "thread",
            "UNIRUN_AUTO": "0",
            "UNIRUN_CPU_BOUND": "yes",
            "UNIRUN_IO_BOUND": "no",
            "UNIRUN_PREFERS_SUBINTERPRETERS": "true",
            "UNIRUN_MAX_WORKERS": "2",
        },
        clear=True,
    ):
        config = RuntimeConfig.from_env()

    assert config.mode == "thread"
    assert config.auto is False
    assert config.cpu_bound is True
    assert config.io_bound is False
    assert config.prefers_subinterpreters is True
    assert config.max_workers == 2


def test_runtime_config_from_env_invalid_values() -> None:
    with mock.patch.dict(
        os.environ,
        {
            "UNIRUN_MODE": "invalid",
            "UNIRUN_AUTO": "maybe",
            "UNIRUN_MAX_WORKERS": "bogus",
        },
        clear=True,
    ):
        config = RuntimeConfig.from_env()

    assert config.mode == "auto"
    assert config.auto is True
    assert config.max_workers is None
