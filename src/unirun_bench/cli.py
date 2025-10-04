from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

from unirun.capabilities import detect_capabilities

from .engine import BenchmarkRecord, format_table, run_suite


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the optional benchmark CLI."""

    parser = argparse.ArgumentParser(
        prog="unirun-bench",
        description="Benchmark helpers for unirun (optional component).",
    )
    parser.add_argument(
        "--profile",
        choices=("cpu", "io", "mixed", "all"),
        default="all",
        help="Subset of scenarios to run",
    )
    parser.add_argument("--samples", type=int, default=5, help="Samples per scenario")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.1,
        help="Blocking duration for IO/mixed workloads",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=150_000,
        help="Upper bound for CPU heavy prime search",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a formatted table",
    )
    parser.add_argument(
        "--show-capabilities",
        action="store_true",
        help="Include runtime capability snapshot in JSON output",
    )
    return parser


def run_benchmarks(args: argparse.Namespace) -> list[BenchmarkRecord]:
    """Execute benchmarks based on parsed CLI arguments."""

    return run_suite(
        profile=args.profile,
        samples=args.samples,
        duration=args.duration,
        limit=args.limit,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point used by ``python -m unirun_bench``."""

    parser = build_parser()
    args = parser.parse_args(argv)
    records = run_benchmarks(args)
    if args.json:
        payload: dict[str, Any] = {
            "records": [asdict(record) for record in records],
        }
        if args.show_capabilities:
            payload["capabilities"] = asdict(detect_capabilities())
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(records))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
