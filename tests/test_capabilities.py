from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from unirun import RuntimeCapabilities, detect_capabilities


def test_detect_capabilities_shape() -> None:
    caps = detect_capabilities()
    assert isinstance(caps, RuntimeCapabilities)
    assert caps.cpu_count >= 1
    assert isinstance(caps.gil_enabled, bool)
    assert isinstance(caps.free_threading_build, bool)
    assert isinstance(caps.supports_subinterpreters, bool)
    major, minor, micro = caps.python_version
    assert all(isinstance(part, int) for part in (major, minor, micro))
    assert caps.python_release.count(".") == 2


def test_detect_capabilities_free_threading_branch() -> None:
    with mock.patch(
        "unirun.capabilities.sysconfig.get_config_var",
        return_value=1,
    ), mock.patch(
        "unirun.capabilities._is_gil_enabled",
        return_value=False,
    ):
        caps = detect_capabilities()
    assert caps.free_threading_build is True
    assert caps.gil_enabled is False
    assert caps.suggested_cpu_workers == caps.cpu_count
    assert caps.suggested_process_workers == max(1, caps.cpu_count - 1)


def test_is_gil_enabled_runtime_error() -> None:
    def raiser() -> None:
        raise RuntimeError("no loop")

    with mock.patch("unirun.capabilities.sys._is_gil_enabled", raiser):
        from unirun.capabilities import _is_gil_enabled

        assert _is_gil_enabled() is True


def test_is_gil_enabled_missing_helper() -> None:
    with mock.patch("unirun.capabilities.sys", SimpleNamespace(_is_gil_enabled=None)):
        from unirun.capabilities import _is_gil_enabled

        assert _is_gil_enabled() is True
