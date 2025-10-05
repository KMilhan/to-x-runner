from __future__ import annotations

from collections.abc import Iterator

import pytest

from unirun import RuntimeConfig, configure, reset


@pytest.fixture(autouse=True)
def restore_runtime() -> Iterator[None]:
    reset()
    configure(RuntimeConfig())
    yield
    configure(RuntimeConfig())
    reset()
