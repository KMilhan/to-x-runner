"""Unit tests for the mutation badge generator helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    """Import the badge script as a module so tests can access helpers."""

    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "update_mutation_badge.py"
    )
    spec = importlib.util.spec_from_file_location("update_mutation_badge", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_badge = _load_module()


def test_parse_results_handles_legacy_summary() -> None:
    """Ensure the parser keeps working with the older mutmut summary block."""

    sample = (
        "Survived 2 mutants.\n"
        "Killed 18 mutants.\n"
        "Timeout 1.\n"
        "Suspicious 3.\n"
        "Incompetent 4.\n"
    )
    counts = _badge._parse_results(sample)
    assert counts == (2, 18, 1, 3, 4)


def test_parse_results_handles_per_mutant_listing() -> None:
    """Confirm the parser tallies modern per-mutant status lines."""

    sample = (
        "module.x: survived\n"
        "module.y: killed\n"
        "module.z: timeout\n"
        "module.q: suspicious\n"
        "module.w: no tests\n"
    )
    counts = _badge._parse_results(sample)
    assert counts == (1, 1, 1, 1, 1)
