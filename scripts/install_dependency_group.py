#!/usr/bin/env python3
"""Install a dependency group using uv regardless of CLI support on the runner."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def load_group(group: str) -> list[str]:
    project = Path("pyproject.toml")
    data = tomllib.loads(project.read_text(encoding="utf-8"))
    groups = data.get("dependency-groups") or {}
    if group not in groups:
        raise SystemExit(f"Dependency group '{group}' not found in pyproject.toml.")
    deps = groups[group]
    if not isinstance(deps, list):
        raise SystemExit(f"Dependency group '{group}' must be a list of requirements.")
    return [str(item) for item in deps]


def install_group(group: str, python_version: str) -> None:
    deps = load_group(group)
    if not deps:
        return
    cmd = ["uv", "pip", "install", "--python", python_version, *deps]
    subprocess.run(cmd, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install one of the pyproject dependency groups using uv pip."
    )
    parser.add_argument("--group", default="dev", help="Dependency group to install.")
    parser.add_argument(
        "--python",
        required=True,
        help="Target Python version used for the uv-managed environment.",
    )
    args = parser.parse_args(argv)
    try:
        install_group(args.group, args.python)
    except subprocess.CalledProcessError as exc:  # pragma: no cover
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
