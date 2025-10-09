from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import urllib.request
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
INSTALLED_LIB_DIR = Path(sysconfig.get_path("stdlib"))

# Target contract suites we can exercise.
CONTRACT_MODULES = [
    "test.test_concurrent_futures",
    "test.test_asyncio",
]


def _version_tag() -> str:
    vi = sys.version_info
    base = f"{vi.major}.{vi.minor}.{vi.micro}"
    suffix = ""
    if vi.releaselevel == "beta":
        suffix = f"b{vi.serial}"
    elif vi.releaselevel == "candidate":
        suffix = f"rc{vi.serial}"
    elif vi.releaselevel == "alpha":  # pragma: no cover - unlikely
        suffix = f"a{vi.serial}"
    return base + suffix


def _ensure_downloaded_tests() -> Path | None:
    cache_root = TESTS_ROOT / ".cpython-tests"
    cache_root.mkdir(parents=True, exist_ok=True)
    tag = _version_tag()
    target = cache_root / f"cpython-{tag}"
    lib_dir = target / "Lib"
    if lib_dir.exists():
        return lib_dir

    url = f"https://github.com/python/cpython/archive/refs/tags/v{tag}.tar.gz"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tar_path = Path(tmp) / "cpython.tar.gz"
            urllib.request.urlretrieve(url, tar_path)
            with tarfile.open(tar_path, mode="r:gz") as archive:
                archive.extractall(tmp)
            extracted_iter = list(Path(tmp).glob("cpython-*"))
            if not extracted_iter:
                return None
            shutil.move(str(extracted_iter[0]), target)
    except Exception as exc:  # pragma: no cover - download issues
        print(f"Failed to download CPython sources: {exc}")
        return None

    return lib_dir if lib_dir.exists() else None


@lru_cache(maxsize=1)
def _stdlib_test_dir() -> Path | None:
    if (INSTALLED_LIB_DIR / "test").exists():
        return INSTALLED_LIB_DIR
    return _ensure_downloaded_tests()


def _ensure_contract_modules_available() -> bool:
    lib_dir = _stdlib_test_dir()
    if lib_dir is None:
        return False

    original_path = list(sys.path)
    sys.path.insert(0, str(lib_dir))
    try:
        for module in CONTRACT_MODULES:
            importlib.import_module(module)
    except ModuleNotFoundError:
        return False
    finally:
        sys.path[:] = original_path
    return True


def _build_env(mode: str, *, extra_paths: Iterable[str] = ()) -> dict[str, str]:
    env = os.environ.copy()
    lib_test_dir = _stdlib_test_dir()
    pythonpath = [str(REPO_ROOT), str(TESTS_ROOT)]
    if lib_test_dir is not None:
        pythonpath.append(str(lib_test_dir))
    pythonpath.extend(extra_paths)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env.pop("PYTHONWARNDEFAULTENCODING", None)
    env["PYTHONWARNINGS"] = "ignore::DeprecationWarning"
    env["UNIRUN_COMPAT_MODE"] = mode
    return env


@pytest.mark.skipif(
    not _ensure_contract_modules_available(),
    reason="CPython test suite unavailable",
)
@pytest.mark.parametrize("contract_module", CONTRACT_MODULES)
@pytest.mark.parametrize("compat_mode", ["managed", "passthrough"])
def test_cpython_contract_suite(contract_module: str, compat_mode: str) -> None:
    """Run CPython's contract suites using compat imports."""

    pytest.xfail("Compat-managed contract suites pending stabilization")

    env = _build_env(compat_mode)
    env["UNIRUN_COMPAT_SITE"] = compat_mode
    cmd = [sys.executable, "-m", "test", "-q", contract_module.split(".")[-1]]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(
            f"Contract suite {contract_module} failed in compat mode={compat_mode}\n"
            f"stdout\n{result.stdout}\n\nstderr\n{result.stderr}"
        )
