from __future__ import annotations

from unirun import DecisionTrace, Run


def test_run_trace_callback_invoked() -> None:
    traces: list[DecisionTrace] = []

    with Run(flavor="threads", trace=traces.append) as executor:
        assert executor.submit(lambda: 2 * 2).result() == 4

    assert len(traces) == 1
    assert traces[0].resolved_mode in {"thread", "none"}


def test_run_trace_with_decision_trace_object() -> None:
    sink = DecisionTrace(mode="", hints={}, resolved_mode="", reason="")

    with Run(flavor="threads", trace=sink):
        pass

    assert sink.resolved_mode in {"thread", "none"}
    assert "thread" in sink.reason or sink.reason
