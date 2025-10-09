from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

BASELINE_PATH = Path(__file__).parent / "data" / "compat_parity.json"

with BASELINE_PATH.open(encoding="utf-8") as fh:
    BASELINE = json.load(fh)


def _public_exports(module):
    names = getattr(module, "__all__", None)
    if names is None:
        names = [name for name in dir(module) if not name.startswith("_")]
    return sorted(set(names))


@pytest.mark.parametrize(
    "stdlib_name, compat_name",
    [
        ("concurrent.futures", "unirun.compat.concurrent.futures"),
        ("asyncio", "unirun.compat.asyncio"),
    ],
)
def test_compat_parity(stdlib_name: str, compat_name: str) -> None:
    baseline = BASELINE[stdlib_name]
    stdlib_module = importlib.import_module(stdlib_name)
    compat_module = importlib.import_module(compat_name)

    stdlib_exports = _public_exports(stdlib_module)
    compat_exports = _public_exports(compat_module)

    regen_hint = "run scripts/update_compat_parity.py"
    assert stdlib_exports == baseline["stdlib"], (
        f"Stdlib exports changed; {regen_hint}"
    )
    assert compat_exports == baseline["compat"], (
        f"Compat exports changed; {regen_hint}"
    )

    missing = sorted(set(stdlib_exports) - set(compat_exports))
    extra = sorted(set(compat_exports) - set(stdlib_exports))

    assert missing == baseline["missing_in_compat"], (
        "Unexpected missing stdlib symbols in compat"
    )
    assert extra == baseline["extra_in_compat"], (
        "Unexpected extra symbols exported by compat"
    )
