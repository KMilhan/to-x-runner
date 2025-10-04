from __future__ import annotations

import pytest

from unirun import RuntimeConfig, configure, reset


@pytest.fixture(autouse=True)
def restore_runtime() -> None:
    reset()
    configure(RuntimeConfig())
    yield
    configure(RuntimeConfig())
    reset()
