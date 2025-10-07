"""Harness for exercising CPython's regression tests against unirun."""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Mapping, MutableMapping, Sequence

import pytest

pytestmark = [
    pytest.mark.cpython_contract,
    pytest.mark.slow,
]

_COMPAT_ALIASES: Mapping[str, str] = {
    "asyncio": "unirun.compat.asyncio",
    "concurrent": "unirun.compat.concurrent",
    "concurrent.futures": "unirun.compat.concurrent.futures",
}

_CONTRACT_MODULES: Sequence[tuple[str, Sequence[str]]] = (
    ("test.concurrent_futures", ("concurrent", "concurrent.futures")),
    ("test.test_asyncio", ("asyncio",)),
)


@dataclass
class ContractWaiver:
    """Represents a deviation from the CPython contract suite."""

    outcome: str
    test_id: str
    detail: str


@dataclass
class ContractReport:
    """Aggregates the waivers collected while running a contract module."""

    module: str
    waivers: Sequence[ContractWaiver]

    def format_summary(self) -> str:
        """Compose a human-readable waiver summary for pytest."""

        lines = [f"CPython contract deviations in {self.module}:"]
        for waiver in self.waivers:
            lines.append(f"- {waiver.outcome} {waiver.test_id}: {waiver.detail}")
        return "\n".join(lines)


def _ensure_contract_module(module_name: str) -> None:
    """Skip gracefully when the requested CPython module is not installed."""

    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        spec = None
    if spec is None:
        pytest.skip(f"CPython regression module {module_name} is unavailable")


def _resolve_compat_aliases(required_aliases: Iterable[str]) -> Mapping[str, types.ModuleType]:
    """Resolve compat modules that should shadow standard-library imports."""

    resolved: Dict[str, types.ModuleType] = {}
    for alias in required_aliases:
        target = _COMPAT_ALIASES.get(alias)
        if target is None:
            raise KeyError(f"unsupported compat alias: {alias}")
        try:
            spec = importlib.util.find_spec(target)
        except ModuleNotFoundError:
            spec = None
        if spec is None:
            pytest.skip(f"compat module {target} is unavailable for {alias}")
        resolved[alias] = importlib.import_module(target)
    return resolved


@contextlib.contextmanager
def _patched_modules(modules: Mapping[str, types.ModuleType]) -> Iterator[None]:
    """Temporarily install compat modules into ``sys.modules``."""

    previous: MutableMapping[str, types.ModuleType | None]
    previous = {name: sys.modules.get(name) for name in modules}
    try:
        for name, module in modules.items():
            sys.modules[name] = module
        for name, module in modules.items():
            if "." not in name:
                continue
            parent_name, attr = name.split(".", 1)
            parent = sys.modules.get(parent_name)
            if parent is not None and getattr(parent, attr, None) is None:
                setattr(parent, attr, module)
        yield
    finally:
        for name in reversed(tuple(modules.keys())):
            original = previous[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def _load_contract_suite(module_name: str) -> unittest.TestSuite:
    """Load the unittest suite from the requested CPython module."""

    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    loader = unittest.defaultTestLoader
    return loader.loadTestsFromModule(module)


def _gather_waivers(result: unittest.TestResult) -> Sequence[ContractWaiver]:
    """Collect failures, errors, and unexpected successes as waivers."""

    waivers: list[ContractWaiver] = []
    for testcase, detail in result.failures:
        waivers.append(ContractWaiver("FAIL", testcase.id(), _short_detail(detail)))
    for testcase, detail in result.errors:
        waivers.append(ContractWaiver("ERROR", testcase.id(), _short_detail(detail)))
    for testcase in result.unexpectedSuccesses:
        waivers.append(ContractWaiver("UNEXPECTED-SUCCESS", testcase.id(), "unexpected success"))
    return waivers


def _short_detail(detail: str) -> str:
    """Summarise a traceback into a single line."""

    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    if not lines:
        return "see test output"
    return lines[-1]


def _run_contract_module(module_name: str, required_aliases: Iterable[str]) -> ContractReport:
    """Execute a contract module while compat modules shadow stdlib imports."""

    compat_modules = _resolve_compat_aliases(required_aliases)
    suite = _load_contract_suite(module_name)
    with _patched_modules(compat_modules):
        result = unittest.TestResult()
        suite.run(result)
    return ContractReport(module=module_name, waivers=_gather_waivers(result))


@pytest.mark.parametrize(
    ("module_name", "required_aliases"),
    _CONTRACT_MODULES,
    ids=("concurrent_futures", "asyncio"),
)
def test_cpython_contracts(module_name: str, required_aliases: Sequence[str]) -> None:
    """Run CPython's regression tests and record deviations as waivers."""

    _ensure_contract_module(module_name)
    report = _run_contract_module(module_name, required_aliases)
    if report.waivers:
        pytest.xfail(report.format_summary())
