"""Generate a shields.io badge that reports mutmut survivability."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
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

_STATUS_NORMALIZATION: Final[dict[str, str]] = {
    "survived": "survived",
    "killed": "killed",
    "timeout": "timeout",
    "timed out": "timeout",
    "suspicious": "suspicious",
    "incompetent": "incompetent",
    "no tests": "incompetent",
    "not checked": "incompetent",
    "skipped": "incompetent",
    "check was interrupted by user": "suspicious",
    "segfault": "suspicious",
}

_UNKNOWN_STATUS_FALLBACK: Final[str] = "incompetent"


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
    """Extract mutmut counters, supporting both legacy and modern formats."""

    try:
        return _parse_summary_block(output)
    except RuntimeError:
        return _parse_per_mutant_statuses(output)


def _parse_summary_block(output: str) -> tuple[int, int, int, int, int]:
    """Parse the historical summary table that mutmut used to print."""

    match = _MUTMUT_RESULTS_PATTERN.search(output)
    if not match:
        raise RuntimeError("Unable to parse mutmut summary block")
    survived = int(match.group("survived"))
    killed = int(match.group("killed"))
    timeout = int(match.group("timeout"))
    suspicious = int(match.group("suspicious"))
    incompetent = int(match.group("incompetent"))
    return survived, killed, timeout, suspicious, incompetent


def _parse_per_mutant_statuses(output: str) -> tuple[int, int, int, int, int]:
    """Aggregate counts from the per-mutant lines mutmut 3.3+ emits."""

    counts: Counter[str] = Counter()
    unknown_statuses: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        _, status_fragment = line.rsplit(":", 1)
        normalized = _STATUS_NORMALIZATION.get(
            status_fragment.strip().lower(),
        )
        if not normalized:
            normalized = _UNKNOWN_STATUS_FALLBACK
            unknown_statuses.add(status_fragment.strip())
        counts[normalized] += 1

    if unknown_statuses:
        joined = ", ".join(sorted(unknown_statuses))
        print(
            f"Encountered unrecognized mutmut statuses: {joined}. "
            f"Treating them as {_UNKNOWN_STATUS_FALLBACK}.",
            file=sys.stderr,
        )

    if not counts:
        raise RuntimeError("Unable to parse mutmut per-mutant statuses")

    survived = counts["survived"]
    killed = counts["killed"]
    timeout = counts["timeout"]
    suspicious = counts["suspicious"]
    incompetent = counts["incompetent"]
    return survived, killed, timeout, suspicious, incompetent


def _run_mutmut_results(mutmut_bin: str) -> str:
    """Return the CLI output for ``mutmut results``."""

    commands = (
        [mutmut_bin, "results", "--all", "true"],
        [mutmut_bin, "results"],
    )
    last_error: subprocess.CalledProcessError | None = None
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            last_error = exc
            continue
        return completed.stdout
    assert last_error is not None
    raise last_error


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
