from __future__ import annotations

import math
import os
import pickle
import queue
import threading
import warnings
from concurrent.futures import Future
from types import SimpleNamespace
from unittest import mock

import pytest

from unirun import interpreter_executor, thread_executor
from unirun.executors import subinterpreter
from unirun.workloads import simulate_blocking_io


def test_interpreter_executor_runs_tasks() -> None:
    if subinterpreter.interpreters is None:
        pytest.skip("sub-interpreters unavailable")  # pragma: no cover
    with warnings.catch_warnings(record=True) as captured:
        executor = interpreter_executor()
    assert captured == []
    assert executor is not thread_executor()
    assert math.isclose(executor.submit(simulate_blocking_io, 0.0).result(), 0.0)


def test_interpreter_executor_with_module(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyInterpreters:
        def __init__(self) -> None:
            self.create = mock.Mock(side_effect=RuntimeError("unsupported"))

    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        DummyInterpreters(),
        raising=False,
    )

    def raiser(*_args: object, **_kwargs: object) -> None:
        raise subinterpreter.SubInterpreterUnavailable("missing support")

    monkeypatch.setattr(subinterpreter, "_create_subinterpreter_executor", raiser)
    with pytest.warns(RuntimeWarning):
        interpreter_exec = interpreter_executor()
    assert interpreter_exec is thread_executor()


def _make_stub_executor() -> subinterpreter.SubInterpreterExecutor:
    executor = object.__new__(subinterpreter.SubInterpreterExecutor)
    executor._tasks = queue.SimpleQueue()
    executor._pending = set()
    executor._pending_lock = threading.Lock()
    executor._shutdown = False
    executor._shutdown_lock = threading.Lock()
    executor._interpreters = []
    executor._threads = []
    return executor


def test_subinterpreter_execution_error_metadata() -> None:
    err = subinterpreter.SubInterpreterExecutionError("pkg", "Err", (1,), "trace")
    assert err.remote_module == "pkg"
    assert err.remote_name == "Err"
    assert err.remote_args == (1,)
    assert err.remote_traceback == "trace"


def test_get_interpreter_executor_warns_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subinterpreter, "interpreters", None, raising=False)
    subinterpreter.reset_interpreter_executor()
    with pytest.warns(RuntimeWarning):
        first = subinterpreter.get_interpreter_executor()
    assert first is thread_executor()
    with warnings.catch_warnings(record=True) as captured:
        second = subinterpreter.get_interpreter_executor()
    assert captured == []
    assert second is thread_executor()
    subinterpreter.reset_interpreter_executor()


def test_subinterpreter_executor_requires_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subinterpreter, "interpreters", None, raising=False)
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)


def test_subinterpreter_executor_requires_primitives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(create=lambda **_: None),
        raising=False,
    )
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)


def test_subinterpreter_shutdown_blocks_new_submissions() -> None:
    if subinterpreter.interpreters is None:
        pytest.skip("sub-interpreters unavailable")  # pragma: no cover
    executor = interpreter_executor()
    try:
        executor.shutdown()
        with pytest.raises(RuntimeError):
            executor.submit(simulate_blocking_io, 0.0)
    finally:
        subinterpreter.reset_interpreter_executor()


def test_subinterpreter_shutdown_cancels_pending() -> None:
    stub = _make_stub_executor()
    future: Future[int] = Future()
    stub._pending.add(future)
    stub.shutdown(cancel_futures=True)
    assert future.cancelled()
    stub.shutdown()


def test_worker_skips_cancelled_future(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _make_stub_executor()
    future: Future[int] = Future()
    future.cancel()
    stub._tasks.put((future, lambda: 1, (), {}))
    stub._tasks.put(subinterpreter._SENTINEL)
    monkeypatch.setattr(subinterpreter, "interpreters", SimpleNamespace())
    stub._worker(object())


def test_worker_uses_run_method(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubInterpreter:
        def run(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    class StubModule:
        def __init__(self) -> None:
            self.created = 0

        def create(self, *args, **kwargs):
            self.created += 1
            return StubInterpreter()

    module = StubModule()
    module.run_string = None
    monkeypatch.setattr(subinterpreter, "interpreters", module, raising=False)
    monkeypatch.setattr(subinterpreter, "_register_atexit", lambda: None)
    executor = subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)
    try:
        assert executor.submit(lambda: 21 * 2).result() == 42
    finally:
        executor.shutdown()


def test_execute_with_run_string_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubModule:
        def create(self, *args, **kwargs):
            return object()

        def run_string(self, interpreter, script):
            return None  # pragma: no cover

    monkeypatch.setattr(subinterpreter, "interpreters", StubModule(), raising=False)
    executor = subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)
    try:
        target = executor._interpreters[0]
        with pytest.raises(subinterpreter.SubInterpreterUnavailable):
            executor._execute_with_run_string(target, lambda: None, (), {})
    finally:
        executor.shutdown()


def test_encode_payload_rejects_unpickleable_callable() -> None:
    executor = _make_stub_executor()
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        executor._encode_payload(lambda: None, (), {})


def test_encode_payload_rejects_unpickleable_argument() -> None:
    executor = _make_stub_executor()
    lock = threading.Lock()
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        executor._encode_payload(abs, (lock,), {})


def test_rebuild_exception_success_and_fallback() -> None:
    executor = _make_stub_executor()
    success = executor._rebuild_exception(
        {
            "exc_module": "builtins",
            "exc_type": "ValueError",
            "exc_args": ("boom",),
            "traceback": "trace",
        }
    )
    assert isinstance(success, ValueError)
    assert success._unirun_remote_traceback == "trace"

    fallback = executor._rebuild_exception(
        {
            "exc_module": "not_a_module",
            "exc_type": "Missing",
            "exc_args": (),
            "traceback": "trace",
        }
    )
    assert isinstance(fallback, subinterpreter.SubInterpreterExecutionError)

    minimal = executor._rebuild_exception(
        {
            "exc_module": "builtins",
            "exc_type": "RuntimeError",
            "exc_args": (),
            "traceback": "",
        }
    )
    assert not hasattr(minimal, "_unirun_remote_traceback")


def test_warn_subinterpreter_fallback_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subinterpreter, "_FALLBACK_WARNED", False)
    with pytest.warns(RuntimeWarning):
        subinterpreter._warn_subinterpreter_fallback("first")
    with warnings.catch_warnings(record=True) as captured:
        subinterpreter._warn_subinterpreter_fallback("second")
    assert captured == []
    subinterpreter._FALLBACK_WARNED = False


def test_store_executor_records_settings() -> None:
    executor = object()
    subinterpreter._store_executor(executor, max_workers=2, isolated=False)
    assert subinterpreter._INTERPRETER_EXECUTOR is executor
    assert subinterpreter._EXECUTOR_SETTINGS == {"max_workers": 2, "isolated": False}


def test_should_rebuild_detection() -> None:
    settings = {"max_workers": 2, "isolated": True}
    assert subinterpreter._should_rebuild(settings, 3, True) is True
    assert subinterpreter._should_rebuild(settings, None, False) is True
    assert subinterpreter._should_rebuild(settings, None, True) is False


def test_create_subinterpreter_executor_pass_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising(**_: object) -> subinterpreter.SubInterpreterExecutor:
        raise subinterpreter.SubInterpreterUnavailable("x")

    monkeypatch.setattr(subinterpreter, "SubInterpreterExecutor", raising)
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        subinterpreter._create_subinterpreter_executor(max_workers=None, isolated=True)


def test_create_subinterpreter_executor_wraps_other_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**_: object) -> subinterpreter.SubInterpreterExecutor:
        raise ValueError("boom")

    monkeypatch.setattr(subinterpreter, "SubInterpreterExecutor", explode)
    with pytest.raises(subinterpreter.SubInterpreterUnavailable) as excinfo:
        subinterpreter._create_subinterpreter_executor(max_workers=None, isolated=True)
    assert "boom" in str(excinfo.value)


def test_destroy_interpreter_uses_close(monkeypatch: pytest.MonkeyPatch) -> None:
    closer = mock.Mock()
    interpreter = SimpleNamespace(close=closer)
    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(destroy=None),
        raising=False,
    )
    executor = _make_stub_executor()
    executor._destroy_interpreter(interpreter)
    closer.assert_called_once_with()


def test_get_interpreter_executor_reuses_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0
    fake_executor = object()

    def fake_create(**_: object) -> object:
        nonlocal call_count
        call_count += 1
        return fake_executor

    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(
            create=lambda **_: None,
            run_string=lambda *args, **kwargs: None,
        ),
        raising=False,
    )
    monkeypatch.setattr(subinterpreter, "_create_subinterpreter_executor", fake_create)
    monkeypatch.setattr(subinterpreter, "_register_atexit", lambda: None)
    subinterpreter.reset_interpreter_executor()
    first = subinterpreter.get_interpreter_executor(max_workers=1)
    second = subinterpreter.get_interpreter_executor(max_workers=1)
    assert first is fake_executor
    assert second is fake_executor
    assert call_count == 1
    subinterpreter.reset_interpreter_executor()


def test_subinterpreter_executor_respects_max_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyThread:
        def __init__(self, *_, **kwargs) -> None:
            self.started = False
            self._target = kwargs.get("target")
            self._args = kwargs.get("args", ())

        def start(self) -> None:
            self.started = True

        def join(self, *_, **__) -> None:
            return None

    class StubModule:
        def __init__(self) -> None:
            self.created = 0
            self.run_string = lambda *_args, **_kwargs: None

        def create(self, *_, **__):
            self.created += 1
            return SimpleNamespace()

    monkeypatch.setattr(subinterpreter, "interpreters", StubModule(), raising=False)
    monkeypatch.setattr(subinterpreter, "_register_atexit", lambda: None)
    monkeypatch.setattr(subinterpreter.threading, "Thread", DummyThread)
    monkeypatch.setattr(
        subinterpreter.SubInterpreterExecutor,
        "_destroy_interpreter",
        lambda self, interp: None,
    )
    executor = subinterpreter.SubInterpreterExecutor(max_workers=2, isolated=True)
    try:
        assert executor._max_workers == 2
        assert len(executor._threads) == 2
        assert all(getattr(thread, "started", False) for thread in executor._threads)
    finally:
        executor.shutdown()


def test_subinterpreter_executor_defaults_to_cpu_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyThread:
        def __init__(self, *_, **kwargs) -> None:
            self.started = False

        def start(self) -> None:
            self.started = True

        def join(self, *_, **__) -> None:
            return None

    class StubModule:
        def __init__(self) -> None:
            self.run_string = lambda *_args, **_kwargs: None

        def create(self, *_, **__):
            return SimpleNamespace()

    monkeypatch.setattr(subinterpreter, "interpreters", StubModule(), raising=False)
    monkeypatch.setattr(subinterpreter, "_register_atexit", lambda: None)
    monkeypatch.setattr(subinterpreter.threading, "Thread", DummyThread)
    monkeypatch.setattr(subinterpreter, "os", SimpleNamespace(cpu_count=lambda: 4))
    monkeypatch.setattr(
        subinterpreter.SubInterpreterExecutor,
        "_destroy_interpreter",
        lambda self, interp: None,
    )
    executor = subinterpreter.SubInterpreterExecutor(max_workers=0, isolated=True)
    try:
        assert executor._max_workers == 4
        assert len(executor._threads) == 4
    finally:
        executor.shutdown()


def test_subinterpreter_executor_handles_zero_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if subinterpreter.interpreters is None:
        monkeypatch.setattr(
            subinterpreter,
            "interpreters",
            SimpleNamespace(
                create=lambda **_: None,
                run_string=lambda *_args, **_kwargs: None,
            ),
            raising=False,
        )
    monkeypatch.setattr(subinterpreter, "range", lambda *_: [], raising=False)
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)


def test_execute_with_run_string_error_result(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubModule:
        def create(self, *args, **kwargs):
            return object()

        def run_string(self, interpreter, script):
            fd = int(script.split("os.fdopen(")[1].split(",")[0])
            outcome = {
                "ok": False,
                "exc_module": "builtins",
                "exc_type": "RuntimeError",
                "exc_args": ("error",),
                "traceback": "trace",
            }
            os.write(fd, pickle.dumps(outcome))

    monkeypatch.setattr(subinterpreter, "interpreters", StubModule(), raising=False)
    monkeypatch.setattr(subinterpreter, "_register_atexit", lambda: None)
    executor = subinterpreter.SubInterpreterExecutor(max_workers=1, isolated=True)
    try:
        target = executor._interpreters[0]
        with pytest.raises(RuntimeError) as excinfo:
            executor._execute_with_run_string(target, simulate_blocking_io, (0.0,), {})
        assert str(excinfo.value) == "error"
    finally:
        executor.shutdown()


def test_execute_with_run_string_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_string(interpreter, script):
        fd = int(script.split("os.fdopen(")[1].split(",")[0])
        os.close(fd)

    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(run_string=fake_run_string),
        raising=False,
    )
    executor = _make_stub_executor()
    with pytest.raises(subinterpreter.SubInterpreterUnavailable):
        executor._execute_with_run_string(object(), simulate_blocking_io, (), {})


def test_subinterpreter_submit_after_shutdown() -> None:
    executor = _make_stub_executor()
    executor._shutdown = True
    with pytest.raises(RuntimeError):
        executor.submit(lambda: None)


def test_create_interpreter_legacy_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    class LegacyModule:
        def __init__(self) -> None:
            self.modes: list[str] = []

        def create(self, *args, **kwargs):
            if "isolated" in kwargs:
                raise TypeError("legacy signature")
            if args:
                self.modes.append(args[0])
            return SimpleNamespace()

    module = LegacyModule()
    monkeypatch.setattr(subinterpreter, "interpreters", module, raising=False)
    executor = _make_stub_executor()
    executor._isolated = False
    interpreter = executor._create_interpreter()
    assert module.modes == ["legacy"]
    assert isinstance(interpreter, SimpleNamespace)


def test_destroy_interpreter_prefers_destroy(monkeypatch: pytest.MonkeyPatch) -> None:
    destroyed: list[SimpleNamespace] = []

    def destroy(target: SimpleNamespace) -> None:
        destroyed.append(target)

    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(destroy=destroy),
        raising=False,
    )
    executor = _make_stub_executor()
    payload = SimpleNamespace()
    executor._destroy_interpreter(payload)
    assert destroyed == [payload]


def test_worker_prefers_run_string(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = _make_stub_executor()
    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(run_string=object()),
        raising=False,
    )

    result_marker = object()

    def fake_execute(self, interpreter, func, args, kwargs):
        return result_marker

    monkeypatch.setattr(
        executor,
        "_execute_with_run_string",
        fake_execute.__get__(executor, subinterpreter.SubInterpreterExecutor),
    )
    future: Future[object] = Future()
    executor._pending.add(future)
    executor._tasks.put((future, lambda: None, (), {}))
    executor._tasks.put(subinterpreter._SENTINEL)
    executor._worker(SimpleNamespace())
    assert future.result() is result_marker


def test_execute_with_run_string_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_string(interpreter, script):
        fd = int(script.split("os.fdopen(")[1].split(",")[0])
        outcome = {"ok": True, "value": pickle.dumps(42)}
        os.write(fd, pickle.dumps(outcome))

    monkeypatch.setattr(
        subinterpreter,
        "interpreters",
        SimpleNamespace(run_string=fake_run_string),
        raising=False,
    )
    executor = _make_stub_executor()
    assert executor._execute_with_run_string(object(), simulate_blocking_io, (), {}) == 42


def test_reset_interpreter_executor_shuts_down(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyExecutor:
        def __init__(self) -> None:
            self.calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            self.calls.append((wait, cancel_futures))

    dummy = DummyExecutor()
    monkeypatch.setattr(subinterpreter, "_INTERPRETER_EXECUTOR", dummy)
    monkeypatch.setattr(
        subinterpreter,
        "_EXECUTOR_SETTINGS",
        {"max_workers": 1, "isolated": False},
        raising=False,
    )
    subinterpreter.reset_interpreter_executor(cancel_futures=True)
    assert dummy.calls == [(True, True)]
    assert subinterpreter._INTERPRETER_EXECUTOR is None


def test_register_atexit_registers_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    def capture(callback):
        calls.append(callback)
        return callback

    monkeypatch.setattr(subinterpreter, "_ATEEXIT_REGISTERED", False)
    monkeypatch.setattr(subinterpreter.atexit, "register", capture)
    subinterpreter._register_atexit()
    subinterpreter._register_atexit()
    assert calls == [subinterpreter.reset_interpreter_executor]
    subinterpreter._ATEEXIT_REGISTERED = False
