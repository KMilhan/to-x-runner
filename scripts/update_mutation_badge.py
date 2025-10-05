"""Generate a shields.io badge that reports mutmut survivability."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Final

_BADGE_LABEL: Final[str] = "mutation survivability"
_MUTMUT_RESULTS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Survived\s+(?P<survived>\d+)\s+mutants.*?"
    r"Killed\s+(?P<killed>\d+)\s+mutants.*?"
    r"Timeout\s+(?P<timeout>\d+).*?"
    r"Suspicious\s+(?P<suspicious>\d+).*?"
    r"Incompetent\s+(?P<incompetent>\d+)",
    re.DOTALL,
)


def _determine_color(rate: float) -> str:
    """Pick a badge color where lower survivability scores are better."""

    if rate <= 0.2:
        return "brightgreen"
    if rate <= 0.4:
        return "green"
    if rate <= 0.6:
        return "yellow"
    if rate <= 0.8:
        return "orange"
    return "red"


def _parse_results(output: str) -> tuple[int, int, int, int, int]:
    """Extract the raw mutmut counters from CLI output."""

    match = _MUTMUT_RESULTS_PATTERN.search(output)
    if not match:
        raise RuntimeError("Unable to parse mutmut results output")
    survived = int(match.group("survived"))
    killed = int(match.group("killed"))
    timeout = int(match.group("timeout"))
    suspicious = int(match.group("suspicious"))
    incompetent = int(match.group("incompetent"))
    return survived, killed, timeout, suspicious, incompetent


def _run_mutmut_results(mutmut_bin: str) -> str:
    """Return the CLI output for ``mutmut results``."""

    completed = subprocess.run(
        [mutmut_bin, "results"],
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def _maybe_run_mutmut(mutmut_bin: str, skip_run: bool) -> None:
    """Execute ``mutmut run`` unless the caller opts out."""

    if skip_run:
        return
    subprocess.run([mutmut_bin, "run"], check=True)


def _write_badge(output: Path, message: str, color: str) -> None:
    """Persist the badge JSON in the repository."""

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "label": _BADGE_LABEL,
        "message": message,
        "color": color,
        "namedLogo": "biohazard",
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="do not invoke 'mutmut run' before collecting results",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("badges/mutation-survivability.json"),
        help="badge JSON path to update",
    )
    parser.add_argument(
        "--mutmut-bin",
        default="mutmut",
        help="mutmut executable to invoke (defaults to 'mutmut')",
    )
    args = parser.parse_args()

    _maybe_run_mutmut(args.mutmut_bin, args.skip_run)
    output = _run_mutmut_results(args.mutmut_bin)
    survived, killed, timeout, suspicious, incompetent = _parse_results(output)
    total = survived + killed + timeout + suspicious + incompetent
    if total == 0:
        message = "n/a"
        color = "lightgrey"
    else:
        survivors = survived + timeout + suspicious + incompetent
        rate = survivors / total
        message = f"{rate * 100:.1f}%"
        color = _determine_color(rate)
    _write_badge(args.output, message, color)
    print(f"Updated {args.output} with survivability {message}")


if __name__ == "__main__":
    main()
