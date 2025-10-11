"""Derive a benchmark speedup badge from unirun_bench JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

COLORS: Final[tuple[tuple[float, str], ...]] = (
    (1.5, "brightgreen"),
    (1.1, "green"),
    (0.9, "yellow"),
    (0.0, "red"),
)


def _determine_color(ratio: float) -> str:
    for threshold, color in COLORS:
        if ratio >= threshold:
            return color
    return "red"


def _format_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "n/a"
    return f"{ratio:.2f}x"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Benchmark JSON produced by `python -m unirun_bench --json`.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination badge JSON path.",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    records = data.get("records", [])
    ratios: list[float] = []
    for scenario in {r.get("scenario") for r in records}:
        unirun_times = [
            float(r["mean_ms"])
            for r in records
            if r.get("scenario") == scenario
            and str(r.get("mode", "")).startswith("unirun")
        ]
        stdlib_times = [
            float(r["mean_ms"])
            for r in records
            if r.get("scenario") == scenario
            and str(r.get("mode", "")).startswith("stdlib")
        ]
        if not unirun_times or not stdlib_times:
            continue
        fastest_unirun = min(unirun_times)
        fastest_stdlib = min(stdlib_times)
        if fastest_unirun > 0:
            ratios.append(fastest_stdlib / fastest_unirun)

    avg_ratio = sum(ratios) / len(ratios) if ratios else None
    badge = {
        "schemaVersion": 1,
        "label": "benchmark speedup",
        "message": _format_ratio(avg_ratio),
        "color": (
            _determine_color(avg_ratio or 0.0) if avg_ratio is not None else "lightgrey"
        ),
        "namedLogo": "speedtest",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(badge, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
