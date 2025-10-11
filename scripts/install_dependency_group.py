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


def load_project() -> dict[str, object]:
    project = Path("pyproject.toml")
    return tomllib.loads(project.read_text(encoding="utf-8"))


def normalize_dependency(
    name: str,
    sources: dict[str, dict[str, object]] | None,
) -> str:
    source_entry: dict[str, object] | None = None
    if sources:
        raw = sources.get(name)
        if isinstance(raw, dict):
            source_entry = raw

    if not source_entry:
        return name

    git_url = source_entry.get("git")
    if git_url:
        rev = source_entry.get("rev")
        if not isinstance(rev, str) or not rev:
            raise SystemExit(f"Git source for '{name}' requires a non-empty rev.")
        return f"git+{git_url}@{rev}#egg={name}"

    path = source_entry.get("path")
    if path:
        return str(path)

    raise SystemExit(f"Unsupported source override for dependency '{name}'.")


def load_group(group: str) -> list[str]:
    data = load_project()
    groups = data.get("dependency-groups") or {}
    if not isinstance(groups, dict):
        raise SystemExit("Invalid dependency-groups structure in pyproject.toml.")
    raw_deps = groups.get(group)
    if raw_deps is None:
        raise SystemExit(f"Dependency group '{group}' not found in pyproject.toml.")
    if not isinstance(raw_deps, list):
        raise SystemExit(f"Dependency group '{group}' must be a list of requirements.")
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})  # type: ignore[call-arg]
    if not isinstance(sources, dict):
        sources = {}
    normalized = [
        normalize_dependency(str(dep), sources)  # type: ignore[arg-type]
        for dep in raw_deps
    ]
    return normalized


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
