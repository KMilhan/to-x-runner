#!/usr/bin/env python
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, TypedDict, cast

MODULES = {
    "concurrent.futures": "unirun.compat.concurrent.futures",
    "asyncio": "unirun.compat.asyncio",
}

REQUIRED_PARITY_KEYS = (
    "stdlib",
    "compat",
    "missing_in_compat",
    "extra_in_compat",
)


class ModuleParity(TypedDict):
    """Parity snapshot for a stdlib module version."""

    stdlib: list[str]
    compat: list[str]
    missing_in_compat: list[str]
    extra_in_compat: list[str]


Baseline = dict[str, dict[str, ModuleParity]]


def public_exports(module):
    names = getattr(module, "__all__", None)
    if names is None:
        names = [name for name in dir(module) if not name.startswith("_")]
    return sorted(set(names))


def _coerce_versions(entry: Any, *, version_key: str) -> dict[str, ModuleParity]:
    """Normalise legacy or untyped baseline payloads."""

    if not isinstance(entry, dict):
        return {}

    # Handle legacy payloads keyed directly by parity metrics.
    if all(key in entry for key in REQUIRED_PARITY_KEYS):
        return {version_key: cast(ModuleParity, entry)}

    versioned: dict[str, ModuleParity] = {}
    for version, payload in entry.items():
        if not isinstance(version, str) or not isinstance(payload, dict):
            continue
        if all(key in payload for key in REQUIRED_PARITY_KEYS):
            versioned[version] = cast(ModuleParity, payload)
    return versioned


def _load_baseline(path: Path, *, version_key: str) -> Baseline:
    """Load and coerce an existing baseline file if present."""

    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}

    baseline: Baseline = {}
    for stdlib_name, entry in raw.items():
        if not isinstance(stdlib_name, str):
            continue
        versions = _coerce_versions(entry, version_key=version_key)
        if versions:
            baseline[stdlib_name] = versions
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Write compat parity baseline")
    parser.add_argument(
        "--output",
        default=Path("tests/data/compat_parity.json"),
        type=Path,
        help="output JSON path",
    )
    args = parser.parse_args()
    version_key = f"{sys.version_info.major}.{sys.version_info.minor}"
    baseline = _load_baseline(args.output, version_key=version_key)

    for stdlib_name, compat_name in MODULES.items():
        stdlib_mod = importlib.import_module(stdlib_name)
        compat_mod = importlib.import_module(compat_name)
        std_exports = public_exports(stdlib_mod)
        compat_exports = public_exports(compat_mod)
        missing = sorted(set(std_exports) - set(compat_exports))
        extra = sorted(set(compat_exports) - set(std_exports))
        module_entry = baseline.setdefault(stdlib_name, {})
        module_entry[version_key] = {
            "stdlib": std_exports,
            "compat": compat_exports,
            "missing_in_compat": missing,
            "extra_in_compat": extra,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
    args.output.write_text(payload, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
