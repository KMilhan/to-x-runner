from __future__ import annotations

import asyncio
import statistics
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Any

from unirun.api import get_executor, reset, submit
from unirun.capabilities import RuntimeCapabilities, detect_capabilities
from unirun.workloads import count_primes, mixed_workload, simulate_blocking_io


@dataclass(slots=True)
class Scenario(ABC):
    """Base metadata describing a single benchmark scenario."""

    name: str
    workload: str
    parallelism: int
    description: str

    @abstractmethod
    def args(self, *, limit: int, duration: float) -> tuple[tuple, dict]:  # pragma: no cover - abstract
        """Return positional and keyword arguments for the underlying workload."""


@dataclass(slots=True)
class CpuScenario(Scenario):
    """CPU-bound benchmark that counts primes using a naive sieve."""

    def args(self, *, limit: int, duration: float) -> tuple[tuple, dict]:  # noqa: D401
        return (limit,), {}


@dataclass(slots=True)
class IoScenario(Scenario):
    """IO-bound benchmark that sleeps for a configurable duration."""

    def args(self, *, limit: int, duration: float) -> tuple[tuple, dict]:  # noqa: D401
        return (duration,), {}


@dataclass(slots=True)
class MixedScenario(Scenario):
    batches: int

    def args(self, *, limit: int, duration: float) -> tuple[tuple, dict]:
        payload = [(limit, duration) for _ in range(self.batches)]
        return (payload,), {}


@dataclass(slots=True)
class BenchmarkRecord:
    """Structured timing information for a single benchmark run."""

    scenario: str
    mode: str
    samples: int
    parallelism: int
    workload: str
    mean_ms: float
    stdev_ms: float
    min_ms: float
    max_ms: float


def build_scenarios(capabilities: RuntimeCapabilities) -> list[Scenario]:
    """Build canonical benchmark scenarios based on interpreter capabilities.

    Args:
        capabilities: Snapshot of the interpreter's concurrency characteristics.

    Returns:
        A list of scenario definitions that cover CPU, IO, and mixed workloads.
    """

    cpu_workers = max(1, min(8, capabilities.suggested_cpu_workers))
    io_workers = max(4, min(64, capabilities.suggested_io_workers))
    mixed_workers = max(1, min(8, capabilities.suggested_cpu_workers))
    batches = max(2, min(6, capabilities.cpu_count))

    return [
        CpuScenario(
            name="cpu.primes",
            workload="cpu",
            parallelism=cpu_workers,
            description="Prime counting with naive sieve",
        ),
        IoScenario(
            name="io.sleep",
            workload="io",
            parallelism=io_workers,
            description="Blocking sleep to test IO threads",
        ),
        MixedScenario(
            name="mixed.hybrid",
            workload="mixed",
            parallelism=mixed_workers,
            description="Alternating CPU/IO batches",
            batches=batches,
        ),
    ]


def run_suite(
    *,
    profile: str = "all",
    samples: int = 5,
    limit: int = 150_000,
    duration: float = 0.1,
    capabilities: RuntimeCapabilities | None = None,
) -> list[BenchmarkRecord]:
    """Execute the requested benchmark profile and return timing records.

    Args:
        profile: Scenario group to run (``cpu``, ``io``, ``mixed``, or ``all``).
        samples: Number of repetitions per scenario and mode.
        limit: Upper bound for CPU-intensive workloads.
        duration: Blocking duration for IO workloads.
        capabilities: Optional precomputed capability snapshot.

    Returns:
        Timing data for each scenario/mode pair expressed as ``BenchmarkRecord``
        instances.
    """

    capabilities = capabilities or detect_capabilities()
    scenarios = build_scenarios(capabilities)
    selected = _select_scenarios(scenarios, profile)

    records: list[BenchmarkRecord] = []
    for scenario in selected:
        records.extend(
            _run_scenario(
                scenario,
                samples=samples,
                limit=limit,
                duration=duration,
            )
        )
    return records


def _run_scenario(
    scenario: Scenario,
    *,
    samples: int,
    limit: int,
    duration: float,
) -> list[BenchmarkRecord]:
    args, kwargs = scenario.args(limit=limit, duration=duration)

    sync_durations = _measure_sync(
        scenario=scenario,
        samples=samples,
        args=args,
        kwargs=kwargs,
    )
    async_durations = _measure_async(
        scenario=scenario,
        samples=samples,
        args=args,
        kwargs=kwargs,
    )
    stdlib_sync_durations = _measure_stdlib_sync(
        scenario=scenario,
        samples=samples,
        args=args,
        kwargs=kwargs,
    )
    stdlib_async_durations = _measure_stdlib_async(
        scenario=scenario,
        samples=samples,
        args=args,
        kwargs=kwargs,
    )

    sync_record = _build_record(
        scenario,
        mode="unirun.sync",
        samples=samples,
        durations=sync_durations,
    )
    async_record = _build_record(
        scenario,
        mode="unirun.async",
        samples=samples,
        durations=async_durations,
    )
    stdlib_sync_record = _build_record(
        scenario,
        mode=_stdlib_sync_mode(scenario),
        samples=samples,
        durations=stdlib_sync_durations,
    )
    stdlib_async_record = _build_record(
        scenario,
        mode=_stdlib_async_mode(scenario),
        samples=samples,
        durations=stdlib_async_durations,
    )
    return [sync_record, async_record, stdlib_sync_record, stdlib_async_record]


def _measure_sync(
    *,
    scenario: Scenario,
    samples: int,
    args: tuple,
    kwargs: dict,
) -> list[float]:
    durations: list[float] = []
    hints = _executor_hints(scenario)
    func = _dispatch_function(scenario)
    for _ in range(samples):
        start = time.perf_counter()
        executor = get_executor(**hints)
        futures = [
            submit(
                executor,
                func,
                *args,
                **kwargs,
            )
            for _ in range(scenario.parallelism)
        ]
        for future in futures:
            future.result()
        durations.append((time.perf_counter() - start) * 1000.0)
    reset()
    return durations


def _measure_async(
    *,
    scenario: Scenario,
    samples: int,
    args: tuple,
    kwargs: dict,
) -> list[float]:
    async def _runner() -> list[float]:
        durations: list[float] = []
        hints = _executor_hints(scenario)
        func = _dispatch_function(scenario)
        for _ in range(samples):
            start = time.perf_counter()
            executor = get_executor(**hints)
            loop = asyncio.get_running_loop()
            coroutines = [
                loop.run_in_executor(
                    executor,
                    partial(func, *args, **kwargs),
                )
                for _ in range(scenario.parallelism)
            ]
            await asyncio.gather(*coroutines)
            durations.append((time.perf_counter() - start) * 1000.0)
        reset()
        return durations

    return asyncio.run(_runner())


def _measure_stdlib_sync(
    *,
    scenario: Scenario,
    samples: int,
    args: tuple,
    kwargs: dict,
) -> list[float]:
    durations: list[float] = []
    func = _dispatch_function(scenario)
    for _ in range(samples):
        start = time.perf_counter()
        with _create_stdlib_executor(scenario) as executor:
            futures = [executor.submit(func, *args, **kwargs) for _ in range(scenario.parallelism)]
            for future in futures:
                future.result()
        durations.append((time.perf_counter() - start) * 1000.0)
    return durations


def _measure_stdlib_async(
    *,
    scenario: Scenario,
    samples: int,
    args: tuple,
    kwargs: dict,
) -> list[float]:
    async def _runner() -> list[float]:
        durations: list[float] = []
        func = _dispatch_function(scenario)
        for _ in range(samples):
            start = time.perf_counter()
            with _create_stdlib_executor(scenario) as executor:
                loop = asyncio.get_running_loop()
                jobs = [
                    loop.run_in_executor(
                        executor,
                        partial(func, *args, **kwargs),
                    )
                    for _ in range(scenario.parallelism)
                ]
                await asyncio.gather(*jobs)
            durations.append((time.perf_counter() - start) * 1000.0)
        return durations

    return asyncio.run(_runner())


def _create_stdlib_executor(scenario: Scenario) -> ThreadPoolExecutor | ProcessPoolExecutor:
    if isinstance(scenario, IoScenario):
        return ThreadPoolExecutor(
            max_workers=scenario.parallelism,
            thread_name_prefix="unirun-native",
        )
    return ProcessPoolExecutor(max_workers=scenario.parallelism)


def _stdlib_sync_mode(scenario: Scenario) -> str:
    return "stdlib.thread.sync" if isinstance(scenario, IoScenario) else "stdlib.process.sync"


def _stdlib_async_mode(scenario: Scenario) -> str:
    return "stdlib.thread.async" if isinstance(scenario, IoScenario) else "stdlib.process.async"


def _dispatch_function(scenario: Scenario):
    if isinstance(scenario, CpuScenario):
        return count_primes
    if isinstance(scenario, IoScenario):
        return simulate_blocking_io
    if isinstance(scenario, MixedScenario):
        return mixed_workload
    raise ValueError(f"Unknown scenario: {scenario}")


def _build_record(
    scenario: Scenario,
    *,
    mode: str,
    samples: int,
    durations: Iterable[float],
) -> BenchmarkRecord:
    data = list(durations)
    mean = statistics.fmean(data) if data else 0.0
    stdev = statistics.pstdev(data) if len(data) > 1 else 0.0
    return BenchmarkRecord(
        scenario=scenario.name,
        mode=mode,
        samples=samples,
        parallelism=scenario.parallelism,
        workload=scenario.workload,
        mean_ms=mean,
        stdev_ms=stdev,
        min_ms=min(data) if data else 0.0,
        max_ms=max(data) if data else 0.0,
    )


def format_table(records: Sequence[BenchmarkRecord]) -> str:
    """Render benchmark results as a simple fixed-width table."""

    if not records:
        return "No benchmark results available"
    headers = (
        "scenario",
        "mode",
        "samples",
        "parallelism",
        "workload",
        "mean_ms",
        "stdev_ms",
        "min_ms",
        "max_ms",
    )
    rows: list[tuple[str, ...]] = []
    for record in records:
        rows.append(
            (
                record.scenario,
                record.mode,
                str(record.samples),
                str(record.parallelism),
                record.workload,
                f"{record.mean_ms:.3f}",
                f"{record.stdev_ms:.3f}",
                f"{record.min_ms:.3f}",
                f"{record.max_ms:.3f}",
            )
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    border = " ".join("-" * width for width in widths)
    lines = [border]
    header_line = " ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    lines.append(header_line)
    lines.append(border)
    for row in rows:
        lines.append(" ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)))
    lines.append(border)
    return "\n".join(lines)


def _select_scenarios(scenarios: list[Scenario], profile: str) -> list[Scenario]:
    if profile == "all":
        return scenarios
    if profile == "cpu":
        scenario_type = CpuScenario
    elif profile == "io":
        scenario_type = IoScenario
    elif profile == "mixed":
        scenario_type = MixedScenario
    else:
        raise ValueError(f"Unsupported profile: {profile}")
    return [scenario for scenario in scenarios if isinstance(scenario, scenario_type)]


def _executor_hints(scenario: Scenario) -> dict[str, Any]:
    hints: dict[str, Any] = {"max_workers": scenario.parallelism}
    if isinstance(scenario, CpuScenario):
        hints["cpu_bound"] = True
    elif isinstance(scenario, IoScenario):
        hints["io_bound"] = True
    return hints


__all__ = ["run_suite", "format_table", "BenchmarkRecord", "Scenario"]
