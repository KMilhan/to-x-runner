"""Property-based coverage guarding scheduler invariants.

These tests enforce the guarantees documented in issue #23 and ARCHITECTURE.md:
- Given stable capabilities/configuration/hints, `_resolve_mode` must stay pure.
- Force flags must outrank heuristic hints so callers can pin behaviour.
- Thread mode semantics must stay predictable as GIL state toggles.
"""

from __future__ import annotations

import dataclasses

from typing import cast

from hypothesis import given, settings
from hypothesis import strategies as st

import unirun.scheduler as scheduler_module
from unirun.capabilities import RuntimeCapabilities
from unirun.config import RuntimeConfig, ThreadMode


EXECUTOR_MODES = st.sampled_from(["auto", "thread", "process", "subinterpreter", "none"])
THREAD_MODES = st.sampled_from(["auto", "gil", "nogil"])
BOOL_OR_NONE = st.one_of(st.none(), st.booleans())


capabilities_strategy = st.builds(
    RuntimeCapabilities,
    python_version=st.tuples(
        st.integers(min_value=3, max_value=3),
        st.integers(min_value=11, max_value=14),
        st.integers(min_value=0, max_value=10),
    ),
    implementation=st.sampled_from(["CPython"]),
    gil_enabled=st.booleans(),
    free_threading_build=st.booleans(),
    supports_subinterpreters=st.booleans(),
    cpu_count=st.integers(min_value=1, max_value=64),
    suggested_io_workers=st.integers(min_value=1, max_value=96),
    suggested_cpu_workers=st.integers(min_value=1, max_value=96),
    suggested_process_workers=st.integers(min_value=1, max_value=96),
)


config_strategy = st.builds(
    RuntimeConfig,
    mode=EXECUTOR_MODES,
    cpu_bound=BOOL_OR_NONE,
    io_bound=BOOL_OR_NONE,
    prefers_subinterpreters=BOOL_OR_NONE,
    max_workers=st.one_of(st.none(), st.integers(min_value=0, max_value=64)),
    auto=st.booleans(),
    thread_mode=THREAD_MODES,
    force_threads=st.booleans(),
    force_process=st.booleans(),
)


@st.composite
def scheduler_hints(draw: st.DrawFn) -> dict[str, object]:
    hints: dict[str, object] = {}
    if draw(st.booleans()):
        hints["cpu_bound"] = draw(BOOL_OR_NONE)
    if draw(st.booleans()):
        hints["io_bound"] = draw(BOOL_OR_NONE)
    if draw(st.booleans()):
        hints["prefers_subinterpreters"] = draw(BOOL_OR_NONE)
    if draw(st.booleans()):
        hints["force_threads"] = draw(st.booleans())
    if draw(st.booleans()):
        hints["force_process"] = draw(st.booleans())
    if draw(st.booleans()):
        hints["thread_mode"] = draw(THREAD_MODES)
    return hints


@given(
    mode=EXECUTOR_MODES,
    hints=scheduler_hints(),
    config=config_strategy,
    caps=capabilities_strategy,
)
@settings(max_examples=100, deadline=None)
def test_resolve_mode_is_pure(mode: str, hints: dict[str, object], config: RuntimeConfig, caps: RuntimeCapabilities) -> None:
    """Calling `_resolve_mode` twice with identical inputs must return identical tuples."""

    scheduler = scheduler_module.Scheduler(config=config)
    scheduler._capabilities = caps
    first = scheduler._resolve_mode(mode, dict(hints), scheduler.config)
    second = scheduler._resolve_mode(mode, dict(hints), scheduler.config)
    assert first == second


@given(
    mode=EXECUTOR_MODES,
    hints=scheduler_hints(),
    config=config_strategy,
    caps=capabilities_strategy,
    force_process_flag=st.booleans(),
    hint_force_process=st.booleans(),
)
@settings(max_examples=75, deadline=None)
def test_force_threads_overrides_hints(
    mode: str,
    hints: dict[str, object],
    config: RuntimeConfig,
    caps: RuntimeCapabilities,
    force_process_flag: bool,
    hint_force_process: bool,
) -> None:
    """Any explicit force_threads directive (config or hint) must resolve to thread mode."""

    configured = dataclasses.replace(
        config,
        force_threads=True,
        force_process=force_process_flag,
    )
    scheduler = scheduler_module.Scheduler(config=configured)
    scheduler._capabilities = caps
    forced_hints = dict(hints)
    forced_hints["force_threads"] = True
    if hint_force_process:
        forced_hints["force_process"] = True
    resolved_mode, _, _ = scheduler._resolve_mode(mode, forced_hints, configured)
    assert resolved_mode == "thread"


@given(
    mode=EXECUTOR_MODES,
    hints=scheduler_hints(),
    config=config_strategy,
    caps=capabilities_strategy,
)
@settings(max_examples=75, deadline=None)
def test_force_process_wins_when_threads_not_forced(
    mode: str,
    hints: dict[str, object],
    config: RuntimeConfig,
    caps: RuntimeCapabilities,
) -> None:
    """Force process flags should prevail whenever threads stay unfixed."""

    configured = dataclasses.replace(
        config,
        force_threads=False,
        force_process=True,
    )
    scheduler = scheduler_module.Scheduler(config=configured)
    scheduler._capabilities = caps
    forced_hints = {key: value for key, value in hints.items() if key != "force_threads"}
    forced_hints["force_process"] = True
    resolved_mode, _, _ = scheduler._resolve_mode(mode, forced_hints, configured)
    assert resolved_mode == "process"


@given(thread_mode=THREAD_MODES, caps=capabilities_strategy)
@settings(max_examples=75, deadline=None)
def test_thread_mode_cpu_bound_precedence(thread_mode: str, caps: RuntimeCapabilities) -> None:
    """Resolving CPU-bound workloads must respect thread_mode combined with GIL state."""

    base_config = RuntimeConfig(
        mode="auto",
        cpu_bound=None,
        io_bound=None,
        prefers_subinterpreters=False,
        max_workers=None,
        auto=True,
        thread_mode=cast(ThreadMode, thread_mode),
        force_threads=False,
        force_process=False,
    )
    scheduler = scheduler_module.Scheduler(config=base_config)
    hints = {"cpu_bound": True}
    gil_caps = dataclasses.replace(
        caps,
        gil_enabled=True,
        free_threading_build=False,
        supports_subinterpreters=False,
    )
    nogil_caps = dataclasses.replace(
        caps,
        gil_enabled=False,
        free_threading_build=True,
        supports_subinterpreters=False,
    )
    scheduler._capabilities = gil_caps
    gil_mode, _, _ = scheduler._resolve_mode("auto", hints, base_config)
    scheduler._capabilities = nogil_caps
    nogil_mode, _, _ = scheduler._resolve_mode("auto", hints, base_config)
    if thread_mode == "gil":
        assert gil_mode == "process"
        assert nogil_mode == "process"
    elif thread_mode == "nogil":
        assert gil_mode == "thread"
        assert nogil_mode == "thread"
    else:
        assert gil_mode == "process"
        assert nogil_mode == "thread"
