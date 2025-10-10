#!/usr/bin/env python
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

MODULES = {
    "concurrent.futures": "unirun.compat.concurrent.futures",
    "asyncio": "unirun.compat.asyncio",
}


def public_exports(module):
    names = getattr(module, "__all__", None)
    if names is None:
        names = [name for name in dir(module) if not name.startswith("_")]
    return sorted(set(names))


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
    baseline: dict[str, dict[str, dict[str, list[str]]]] = {}
    if args.output.exists():
        baseline = json.loads(args.output.read_text(encoding="utf-8"))

    for stdlib_name in MODULES:
        existing = baseline.get(stdlib_name, {})
        if existing and "stdlib" in existing:
            existing = {version_key: existing}
        baseline[stdlib_name] = existing

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
