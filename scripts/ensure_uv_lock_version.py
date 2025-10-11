#!/usr/bin/env python3
"""Ensure the uv.lock workspace entry sets a concrete version string."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_VERSION = "0.0.0"
PACKAGE_BLOCK = '[[package]]\nname = "unirun"\n'


def _ensure_version(lock_path: Path, *, version: str, check_only: bool) -> int:
    """Insert or validate the version line for the unirun workspace package."""

    if not lock_path.exists():
        print("uv.lock is missing; run `uv lock` before proceeding.", file=sys.stderr)
        return 1

    contents = lock_path.read_text(encoding="utf-8")
    expected_block = f'{PACKAGE_BLOCK}version = "{version}"\n'

    if expected_block in contents:
        return 0

    if PACKAGE_BLOCK not in contents:
        print(
            "Could not locate unirun workspace entry inside uv.lock.",
            file=sys.stderr,
        )
        return 1

    if check_only:
        message = (
            f"uv.lock is missing `version = \"{version}\"` in the workspace block."
        )
        print(message, file=sys.stderr)
        return 1

    updated = contents.replace(PACKAGE_BLOCK, expected_block, 1)
    if updated == contents:
        print("Unable to inject version metadata into uv.lock.", file=sys.stderr)
        return 1

    lock_path.write_text(updated, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure uv.lock records version metadata for the unirun workspace package."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the lockfile already contains the version line.",
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help="Version string to enforce inside uv.lock (default: %(default)s).",
    )
    args = parser.parse_args(argv)
    lock_path = Path("uv.lock")
    return _ensure_version(lock_path, version=args.version, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
