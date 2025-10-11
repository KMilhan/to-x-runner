"""Generate coverage badge payloads from coverage.json output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

BADGE_TEMPLATE: Final[dict[str, object]] = {
    "schemaVersion": 1,
    "label": "",
    "message": "",
    "color": "blue",
    "namedLogo": "pytest",
}


def _determine_color(percent: float) -> str:
    if percent >= 90:
        return "brightgreen"
    if percent >= 80:
        return "green"
    if percent >= 70:
        return "yellow"
    if percent >= 50:
        return "orange"
    return "red"


def _format(percent: float | None) -> str:
    return "n/a" if percent is None else f"{percent:.1f}%"


def _compute_percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return (numerator / denominator) * 100


def _write_badge(path: Path, label: str, percent: float | None) -> None:
    badge = BADGE_TEMPLATE.copy()
    badge["label"] = label
    badge["message"] = _format(percent)
    color = _determine_color(percent or 0) if percent is not None else "lightgrey"
    badge["color"] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage-json",
        default=Path(".coverage.json"),
        type=Path,
        help="Path to the coverage JSON report (default: .coverage.json).",
    )
    parser.add_argument(
        "--lines-badge",
        default=Path("badges/coverage-lines.json"),
        type=Path,
        help="Destination for the line coverage badge JSON.",
    )
    parser.add_argument(
        "--branches-badge",
        default=Path("badges/coverage-branches.json"),
        type=Path,
        help="Destination for the branch coverage badge JSON.",
    )
    args = parser.parse_args()

    data = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    covered_lines = int(totals.get("covered_lines", 0))
    num_statements = int(totals.get("num_statements", 0))
    covered_branches = int(totals.get("covered_branches", 0))
    num_branches = int(totals.get("num_branches", 0))

    line_percent = _compute_percent(covered_lines, num_statements)
    branch_percent = _compute_percent(covered_branches, num_branches)

    _write_badge(args.lines_badge, "coverage (lines)", line_percent)
    _write_badge(args.branches_badge, "coverage (branches)", branch_percent)


if __name__ == "__main__":
    main()
