from __future__ import annotations

import importlib
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Iterable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB_TEST_DIR = Path(sysconfig.get_path("stdlib")) / "test"

# Target contract suites we can exercise.
CONTRACT_MODULES = [
    "test.test_concurrent_futures",
    "test.test_asyncio",
]


def _ensure_contract_modules_available() -> bool:
    for module in CONTRACT_MODULES:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            return False
    return LIB_TEST_DIR.exists()


def _build_env(mode: str, *, extra_paths: Iterable[str] = ()) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = [str(REPO_ROOT), str(LIB_TEST_DIR)]
    pythonpath.extend(extra_paths)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env.pop("PYTHONWARNDEFAULTENCODING", None)
    env["PYTHONWARNINGS"] = "ignore::DeprecationWarning"
    env["UNIRUN_COMPAT_MODE"] = mode
    return env


@pytest.mark.skipif(not _ensure_contract_modules_available(), reason="CPython test suite unavailable")
@pytest.mark.parametrize("contract_module", CONTRACT_MODULES)
@pytest.mark.parametrize("compat_mode", ["managed", "passthrough"])
def test_cpython_contract_suite(contract_module: str, compat_mode: str) -> None:
    """Run CPython's contract suites using compat imports."""

    if compat_mode == "managed":
        pytest.skip("Managed compat CPython suites pending")

    module_name = contract_module.split(".")[-1]
    cmd = [sys.executable, "-m", "unittest", contract_module]
    env = _build_env(compat_mode)
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(
            f"Contract suite {contract_module} failed in compat mode={compat_mode}\n"
            f"stdout\n{result.stdout}\n\nstderr\n{result.stderr}"
        )
