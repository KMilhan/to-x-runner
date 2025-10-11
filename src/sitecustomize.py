"""Sitecustomize hook installing unirun's compat overlays when requested."""

from __future__ import annotations

import importlib
import os
import sys

MODE = os.environ.get("UNIRUN_COMPAT_SITE")
_TEST_PATH = os.environ.get("UNIRUN_COMPAT_TESTPATH")


def _ensure_test_path() -> None:
    if _TEST_PATH and _TEST_PATH not in sys.path:
        sys.path.insert(0, _TEST_PATH)


def _install(module_name: str, alias: str) -> None:
    module = importlib.import_module(module_name)
    sys.modules[alias] = module
    parent_name, _, child_name = alias.rpartition(".")
    if parent_name:
        parent = importlib.import_module(parent_name)
        setattr(parent, child_name, module)


_ensure_test_path()

if MODE == "managed":
    os.environ.setdefault("UNIRUN_COMPAT_MODE", "managed")
    _install("unirun.compat.concurrent.futures", "concurrent.futures")
    _install("unirun.compat.asyncio", "asyncio")
elif MODE == "passthrough":
    os.environ["UNIRUN_COMPAT_MODE"] = "passthrough"
elif MODE in (None, ""):
    pass
else:  # pragma: no cover - defensive guard for unexpected configuration
    raise RuntimeError(f"Unsupported UNIRUN_COMPAT_SITE mode: {MODE}")
