from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import asdict

import pytest


def _mutation_instrumentation_active() -> bool:
    """Detect whether mutmut instrumentation is active in the current process."""

    module = sys.modules.get("mutmut")
    if module is None:
        return False
    config = getattr(module, "config", None)
    if config is None:
        return True
    return bool(getattr(config, "is_running", True))


if _mutation_instrumentation_active():
    pytestmark = pytest.mark.skip(
        reason="mutmut instrumentation breaks multiprocessing trampolines",
    )
else:
    from unirun_bench.engine import BenchmarkRecord, format_table, run_suite


@pytest.mark.skipif(
    _mutation_instrumentation_active(),
    reason="mutmut instrumentation breaks multiprocessing trampolines",
)
def test_run_suite_cpu_profile() -> None:
    records = run_suite(profile="cpu", samples=1, limit=100, duration=0.0)
    expected = {
        ("cpu.primes", "unirun.sync"),
        ("cpu.primes", "unirun.async"),
        ("cpu.primes", "stdlib.process.sync"),
        ("cpu.primes", "stdlib.process.async"),
        ("cpu.primes.map", "unirun.map"),
        ("cpu.primes.map", "stdlib.process.map"),
        ("cpu.to_process", "unirun.to_process"),
        ("cpu.to_process", "stdlib.loop.run_in_executor"),
    }
    assert {(record.scenario, record.mode) for record in records} == expected


@pytest.mark.skipif(
    _mutation_instrumentation_active(),
    reason="mutmut instrumentation breaks multiprocessing trampolines",
)
def test_run_suite_other_profiles() -> None:
    io_records = run_suite(profile="io", samples=1, duration=0.0)
    assert {(record.scenario, record.mode) for record in io_records} == {
        ("io.sleep", "unirun.sync"),
        ("io.sleep", "unirun.async"),
        ("io.sleep", "stdlib.thread.sync"),
        ("io.sleep", "stdlib.thread.async"),
        ("io.sleep.map", "unirun.map"),
        ("io.sleep.map", "stdlib.thread.map"),
        ("io.to_thread", "unirun.to_thread"),
        ("io.to_thread", "stdlib.asyncio.to_thread"),
    }
    mixed_records = run_suite(profile="mixed", samples=1, limit=50, duration=0.0)
    assert {(record.scenario, record.mode) for record in mixed_records} == {
        ("mixed.hybrid", "unirun.sync"),
        ("mixed.hybrid", "unirun.async"),
        ("mixed.hybrid", "stdlib.process.sync"),
        ("mixed.hybrid", "stdlib.process.async"),
    }
    all_records = run_suite(samples=1, limit=50, duration=0.0)
    scenarios = {(record.scenario, record.mode) for record in all_records}
    expected = {
        ("cpu.primes", "unirun.sync"),
        ("cpu.primes", "unirun.async"),
        ("cpu.primes", "stdlib.process.sync"),
        ("cpu.primes", "stdlib.process.async"),
        ("cpu.primes.map", "unirun.map"),
        ("cpu.primes.map", "stdlib.process.map"),
        ("cpu.to_process", "unirun.to_process"),
        ("cpu.to_process", "stdlib.loop.run_in_executor"),
        ("io.sleep", "unirun.sync"),
        ("io.sleep", "unirun.async"),
        ("io.sleep", "stdlib.thread.sync"),
        ("io.sleep", "stdlib.thread.async"),
        ("io.sleep.map", "unirun.map"),
        ("io.sleep.map", "stdlib.thread.map"),
        ("io.to_thread", "unirun.to_thread"),
        ("io.to_thread", "stdlib.asyncio.to_thread"),
        ("mixed.hybrid", "unirun.sync"),
        ("mixed.hybrid", "unirun.async"),
        ("mixed.hybrid", "stdlib.process.sync"),
        ("mixed.hybrid", "stdlib.process.async"),
    }
    assert scenarios == expected


def test_format_table_outputs_rows() -> None:
    record = BenchmarkRecord(
        scenario="cpu.primes",
        mode="sync",
        samples=1,
        parallelism=2,
        workload="cpu",
        mean_ms=1.234,
        stdev_ms=0.0,
        min_ms=1.234,
        max_ms=1.234,
    )
    table = format_table([record])
    for value in asdict(record).values():
        assert str(value)[:5] in table


def test_format_table_no_records() -> None:
    assert format_table([]) == "No benchmark results available"


@pytest.mark.parametrize(
    "use_json, show_caps",
    [(False, False), (True, False), (True, True)],
)
def test_cli_outputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    use_json: bool,
    show_caps: bool,
) -> None:
    from unirun_bench import cli

    fake_record = BenchmarkRecord(
        scenario="cpu.primes",
        mode="unirun.sync",
        samples=1,
        parallelism=1,
        workload="cpu",
        mean_ms=0.1,
        stdev_ms=0.0,
        min_ms=0.1,
        max_ms=0.1,
    )

    monkeypatch.setattr(cli, "run_suite", lambda **kwargs: [fake_record])
    monkeypatch.setattr(cli, "detect_capabilities", lambda: fake_record)

    argv = ["--samples", "1", "--profile", "cpu"]
    if use_json:
        argv.append("--json")
        if show_caps:
            argv.append("--show-capabilities")

    exit_code = cli.main(argv)
    assert exit_code == 0
    output = capsys.readouterr().out
    if use_json:
        assert "records" in output
        if show_caps:
            assert "capabilities" in output
        else:
            assert "capabilities" not in output
    else:
        assert "cpu.primes" in output


def test_select_scenarios_failure() -> None:

    from unirun_bench.engine import CpuScenario, _select_scenarios

    scenario = CpuScenario(
        name="cpu.primes",
        workload="cpu",
        parallelism=1,
        description="",
    )
    with pytest.raises(ValueError):
        _select_scenarios([scenario], "invalid")


def test_dispatch_function_error() -> None:
    from dataclasses import dataclass

    from unirun_bench.engine import Scenario, _dispatch_function

    @dataclass(slots=True)
    class DummyScenario(Scenario):
        def args(self, *, limit: int, duration: float) -> tuple[tuple, dict]:
            return (), {}

        def modes(self) -> Sequence:  # pragma: no cover - used for ABC compliance only
            return ()

    with pytest.raises(ValueError):
        _dispatch_function(
            DummyScenario(
                name="dummy",
                workload="test",
                parallelism=1,
                description="",
            )
        )
    DummyScenario(
        name="dummy",
        workload="test",
        parallelism=1,
        description="",
    ).args(limit=0, duration=0.0)


def test_map_scenario_rejects_unknown_workload() -> None:
    from unirun_bench.engine import MapScenario

    scenario = MapScenario(
        name="mystery",
        workload="mystery",
        parallelism=1,
        description="",
    )
    with pytest.raises(ValueError):
        scenario.args(limit=1, duration=0.0)


def test_mixed_scenario_marks_cpu_bound() -> None:
    from unirun_bench.engine import MixedScenario, _executor_hints

    scenario = MixedScenario(
        name="mixed.hybrid",
        workload="mixed",
        parallelism=2,
        description="",
        batches=2,
    )

    hints = _executor_hints(scenario)

    assert hints["cpu_bound"] is True
    assert hints["max_workers"] == scenario.parallelism


def test_stdlib_benchmarks_reuse_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    from concurrent.futures import Future

    from unirun_bench import engine

    scenario = engine.IoScenario(
        name="io.sleep",
        workload="io",
        parallelism=3,
        description="",
    )

    class DummyExecutor:
        def __init__(self) -> None:
            self.submit_calls = 0
            self.map_calls = 0

        def submit(self, func, *args, **kwargs) -> Future:
            self.submit_calls += 1
            future: Future = Future()
            future.set_result(func(*args, **kwargs))
            return future

        def map(self, func, iterable, *iterables):
            self.map_calls += 1
            yield from map(func, iterable, *iterables, strict=False)

        def shutdown(self, wait: bool = True) -> None:  # noqa: ARG002
            return None

    class DummyContextManager:
        def __init__(self, executor: DummyExecutor) -> None:
            self.executor = executor

        def __enter__(self) -> DummyExecutor:
            return self.executor

        def __exit__(self, exc_type, exc_value, traceback) -> None:  # noqa: ANN001
            self.executor.shutdown()

    created: list[DummyExecutor] = []

    def fake_create_stdlib_executor(_scenario: engine.Scenario) -> DummyContextManager:
        executor = DummyExecutor()
        created.append(executor)
        return DummyContextManager(executor)

    def fake_dispatch(_scenario: engine.Scenario):
        return lambda *args, **kwargs: 0 if not args else args[0]

    monkeypatch.setattr(engine, "_create_stdlib_executor", fake_create_stdlib_executor)
    monkeypatch.setattr(engine, "_dispatch_function", fake_dispatch)

    args, kwargs = scenario.args(limit=0, duration=0.0)
    durations = engine._measure_stdlib_submit_sync(
        scenario=scenario,
        samples=4,
        args=args,
        kwargs=kwargs,
    )

    assert len(durations) == 4
    assert len(created) == 1
    assert created[0].submit_calls == scenario.parallelism * 4

    created.clear()
    map_scenario = engine.MapScenario(
        name="io.sleep.map",
        workload="io",
        parallelism=3,
        description="",
    )
    args, kwargs = map_scenario.args(limit=0, duration=0.0)
    durations = engine._measure_stdlib_map(
        scenario=map_scenario,
        samples=2,
        args=args,
        kwargs=kwargs,
    )

    assert len(durations) == 2
    assert len(created) == 1
    assert created[0].map_calls == 2
