from __future__ import annotations

from unirun.workloads import count_primes, mixed_workload


def test_mixed_workload() -> None:
    result = mixed_workload([(10, 0.0), (5, 0.0)])
    assert len(result) == 2
    assert result[0] > 0


def test_count_primes_low_limit() -> None:
    assert count_primes(0) == 0
