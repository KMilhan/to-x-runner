"""Sitecustomize shim to redirect stdlib modules to unirun compat mirrors."""

from __future__ import annotations

import importlib
import os
import sys

MODE = os.environ.get("UNIRUN_COMPAT_SITE")

if MODE == "managed":
    os.environ.setdefault("UNIRUN_COMPAT_MODE", "managed")
    sys.modules["concurrent.futures"] = importlib.import_module(
        "unirun.compat.concurrent.futures"
    )
    sys.modules["asyncio"] = importlib.import_module("unirun.compat.asyncio")
elif MODE == "passthrough":
    os.environ["UNIRUN_COMPAT_MODE"] = "passthrough"
elif MODE in (None, ""):
    pass
else:  # pragma: no cover - defensive guard for unexpected configuration
    raise RuntimeError(f"Unsupported UNIRUN_COMPAT_SITE mode: {MODE}")
