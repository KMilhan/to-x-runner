"""Write a simple status badge JSON payload."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Final

COLORS: Final[dict[str, str]] = {
    "success": "brightgreen",
    "failure": "red",
    "cancelled": "lightgrey",
}

MESSAGES: Final[dict[str, str]] = {
    "success": "pass",
    "failure": "fail",
    "cancelled": "cancelled",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Badge label text.")
    parser.add_argument(
        "--status",
        choices=("success", "failure", "cancelled"),
        required=True,
        help="Workflow status to encode.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination for the badge JSON.",
    )
    args = parser.parse_args()

    payload = {
        "schemaVersion": 1,
        "label": args.label,
        "message": MESSAGES[args.status],
        "color": COLORS[args.status],
        "namedLogo": "githubactions",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
