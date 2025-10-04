from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict

import pytest

from unirun_bench.engine import BenchmarkRecord, format_table, run_suite


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


@pytest.mark.parametrize("use_json", [False, True])
def test_cli_outputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    use_json: bool,
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
        argv.append("--show-capabilities")

    exit_code = cli.main(argv)
    assert exit_code == 0
    output = capsys.readouterr().out
    if use_json:
        assert "records" in output
        assert "capabilities" in output
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
