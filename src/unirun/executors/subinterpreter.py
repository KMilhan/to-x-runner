from __future__ import annotations

import atexit
import base64
import importlib
import os
import pickle
import queue
import threading
import warnings
from concurrent.futures import Executor, Future
from typing import Any

from . import threading as thread_module

try:
    import interpreters  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - module optional and platform specific
    try:  # pragma: no cover - fallback to private CPython module
        import _interpreters as interpreters  # type: ignore[assignment, import-not-found]
    except Exception:  # pragma: no cover - module optional and platform specific
        interpreters = None  # type: ignore[assignment]


_INTERPRETER_EXECUTOR: Executor | None = None
_EXECUTOR_SETTINGS: dict[str, Any] = {"max_workers": None, "isolated": True}
_LOCK = threading.Lock()
_FALLBACK_WARNED = False
_ATEEXIT_REGISTERED = False
_SENTINEL: object = object()


class SubInterpreterExecutionError(RuntimeError):
    """Wrap exceptions originating from a sub-interpreter call."""

    def __init__(
        self,
        module: str,
        name: str,
        args: tuple[Any, ...],
        traceback_text: str,
    ) -> None:
        message = f"{module}.{name}{args}"
        super().__init__(message)
        self.remote_module = module
        self.remote_name = name
        self.remote_args = args
        self.remote_traceback = traceback_text


class SubInterpreterExecutor(Executor):
    """Minimal executor that routes work through CPython sub-interpreters."""

    def __init__(self, *, max_workers: int | None, isolated: bool) -> None:
        if interpreters is None:
            raise SubInterpreterUnavailable("interpreters module unavailable")
        has_create = hasattr(interpreters, "create")
        has_run_string = hasattr(interpreters, "run_string")
        if not has_create or not has_run_string:
            message = "interpreters module lacks required primitives"
            raise SubInterpreterUnavailable(message)

        cpu_count = os.cpu_count() or 1
        workers = cpu_count
        if max_workers is not None and max_workers > 0:
            workers = max_workers
        self._max_workers = max(1, workers)
        self._isolated = isolated
        self._tasks: queue.SimpleQueue[Any] = queue.SimpleQueue()
        self._threads: list[threading.Thread] = []
        self._interpreters: list[Any] = []
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        self._pending: set[Future[Any]] = set()
        self._pending_lock = threading.Lock()

        for index in range(self._max_workers):
            interp = self._create_interpreter()
            thread = threading.Thread(
                target=self._worker,
                name=f"unirun-subinterp-{index}",
                args=(interp,),
                daemon=True,
            )
            thread.start()
            self._interpreters.append(interp)
            self._threads.append(thread)

        if not self._threads:
            raise SubInterpreterUnavailable("failed to start sub-interpreter workers")

    def submit(self, func: Any, /, *args: Any, **kwargs: Any) -> Future[Any]:
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("sub-interpreter executor has been shut down")

        future: Future[Any] = Future()
        task = (future, func, args, kwargs)
        with self._pending_lock:
            self._pending.add(future)
        self._tasks.put(task)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        with self._shutdown_lock:
            if self._shutdown:
                wait = wait and False
            self._shutdown = True

        if cancel_futures:
            with self._pending_lock:
                pending = tuple(self._pending)
                self._pending.clear()
            for future in pending:
                future.cancel()

        for _ in self._threads:
            self._tasks.put(_SENTINEL)

        if wait:
            for thread in self._threads:
                thread.join()

        for interp in self._interpreters:
            self._destroy_interpreter(interp)
        self._interpreters.clear()
        self._threads.clear()

    # --- internal helpers -------------------------------------------------

    def _create_interpreter(self) -> Any:
        mode: Any
        try:
            return interpreters.create(isolated=self._isolated)  # type: ignore[call-arg, attr-defined]
        except TypeError:
            mode = "isolated" if self._isolated else "legacy"
        except Exception as exc:  # pragma: no cover - interpreter-specific failure
            raise SubInterpreterUnavailable(str(exc)) from exc
        try:
            return interpreters.create(mode)  # type: ignore[call-arg]
        except Exception as exc:  # pragma: no cover - interpreter-specific failure
            raise SubInterpreterUnavailable(str(exc)) from exc

    def _destroy_interpreter(self, interpreter: Any) -> None:
        destroy = getattr(interpreters, "destroy", None)
        if destroy is None:
            close = getattr(interpreter, "close", None)
            if callable(close):  # pragma: no cover - high-level API path
                try:
                    close()
                except Exception:
                    pass
            return
        try:
            destroy(interpreter)  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - interpreter already destroyed
            pass

    def _worker(self, interpreter: Any) -> None:
        run_string = getattr(interpreters, "run_string", None)
        run = getattr(interpreter, "run", None)
        while True:
            task = self._tasks.get()
            if task is _SENTINEL:
                break
            future, func, args, kwargs = task
            with self._pending_lock:
                self._pending.discard(future)
            if not future.set_running_or_notify_cancel():
                continue
            try:
                if run_string is not None and not callable(run):
                    result = self._execute_with_run_string(
                        interpreter,
                        func,
                        args,
                        kwargs,
                    )
                elif callable(run):
                    result = run(func, *args, **kwargs)  # type: ignore[misc]
                else:  # pragma: no cover - unexpected API shape
                    raise SubInterpreterUnavailable("unsupported interpreters API")
            except BaseException as exc:  # pragma: no cover - captured for future
                future.set_exception(exc)
            else:
                future.set_result(result)

    def _execute_with_run_string(
        self,
        interpreter: Any,
        func: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        payload = self._encode_payload(func, args, kwargs)
        r_fd, w_fd = os.pipe()
        script = _SCRIPT_TEMPLATE.format(payload=payload, write_fd=w_fd)
        try:
            interpreters.run_string(interpreter, script)  # type: ignore[call-arg]
        finally:
            try:
                os.close(w_fd)
            except OSError:  # pragma: no cover - descriptor already closed in script
                pass

        with os.fdopen(r_fd, "rb") as reader:
            data = reader.read()

        if not data:
            raise SubInterpreterUnavailable("sub-interpreter returned no data")

        outcome = pickle.loads(data)
        if outcome.get("ok"):
            return pickle.loads(outcome["value"])
        raise self._rebuild_exception(outcome)

    def _encode_payload(
        self,
        func: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        try:
            fn_bytes = pickle.dumps(func)
        except Exception as exc:
            raise SubInterpreterUnavailable(
                "callable must be pickleable for sub-interpreter execution",
            ) from exc
        try:
            args_bytes = pickle.dumps(args)
            kwargs_bytes = pickle.dumps(kwargs)
        except Exception as exc:
            raise SubInterpreterUnavailable(
                "arguments must be pickleable for sub-interpreter execution",
            ) from exc
        payload = {"callable": fn_bytes, "args": args_bytes, "kwargs": kwargs_bytes}
        return base64.b64encode(pickle.dumps(payload)).decode("ascii")

    def _rebuild_exception(self, outcome: dict[str, Any]) -> Exception:
        module = outcome.get("exc_module", "builtins")
        name = outcome.get("exc_type", "RuntimeError")
        args = tuple(outcome.get("exc_args", ()))
        tb = outcome.get("traceback", "")
        try:
            exc_module = importlib.import_module(module)
            exc_cls = getattr(exc_module, name)
            exc = exc_cls(*args)
        except Exception:  # pragma: no cover - fallback for unknown exception types
            exc = SubInterpreterExecutionError(module, name, args, tb)
        else:
            if tb:
                exc._unirun_remote_traceback = tb
        return exc


_SCRIPT_TEMPLATE = """\
import base64
import pickle
import os
import traceback

_payload = pickle.loads(base64.b64decode("{payload}"))
func = pickle.loads(_payload["callable"])
args = pickle.loads(_payload["args"])
kwargs = pickle.loads(_payload["kwargs"])

try:
    value = func(*args, **kwargs)
    try:
        value_bytes = pickle.dumps(value)
    except Exception as exc:
        _result = {{
            "ok": False,
            "exc_module": type(exc).__module__,
            "exc_type": type(exc).__name__,
            "exc_args": exc.args,
            "traceback": traceback.format_exc(),
        }}
    else:
        _result = {{"ok": True, "value": value_bytes}}
except Exception as exc:
    _result = {{
        "ok": False,
        "exc_module": type(exc).__module__,
        "exc_type": type(exc).__name__,
        "exc_args": exc.args,
        "traceback": traceback.format_exc(),
    }}

with os.fdopen({write_fd}, "wb", closefd=True) as pipe:
    pipe.write(pickle.dumps(_result))
"""


def get_interpreter_executor(
    *, max_workers: int | None = None, isolated: bool = True
) -> Executor:
    """Return an executor that routes work through CPython sub-interpreters.

    When the interpreter runtime lacks the necessary support, the function
    downgrades to the shared thread pool and emits a warning so call sites can
    continue to operate without bespoke guards.
    """

    if interpreters is None:
        _warn_subinterpreter_fallback(
            "CPython sub-interpreters are unavailable; using thread executor instead.",
        )
        return thread_module.get_thread_pool(max_workers=max_workers)

    with _LOCK:
        current = _INTERPRETER_EXECUTOR
        settings = dict(_EXECUTOR_SETTINGS)

    if current is not None and not _should_rebuild(settings, max_workers, isolated):
        return current

    try:
        executor = _create_subinterpreter_executor(
            max_workers=max_workers,
            isolated=isolated,
        )
    except SubInterpreterUnavailable as exc:
        _warn_subinterpreter_fallback(
            f"{exc}; using thread executor instead.",
        )
        return thread_module.get_thread_pool(max_workers=max_workers)

    with _LOCK:
        _store_executor(executor, max_workers=max_workers, isolated=isolated)
    _register_atexit()
    return executor


def reset_interpreter_executor(*, cancel_futures: bool = False) -> None:
    """Undo any interpreter pool state (placeholder)."""

    global _INTERPRETER_EXECUTOR, _FALLBACK_WARNED
    with _LOCK:
        executor = _INTERPRETER_EXECUTOR
        _INTERPRETER_EXECUTOR = None
        _EXECUTOR_SETTINGS.update({"max_workers": None, "isolated": True})
        _FALLBACK_WARNED = False
    if executor is not None and hasattr(executor, "shutdown"):
        executor.shutdown(wait=True, cancel_futures=cancel_futures)


class SubInterpreterUnavailable(RuntimeError):
    """Raised when sub-interpreters cannot be used in the current runtime."""


def _should_rebuild(
    settings: dict[str, Any], max_workers: int | None, isolated: bool
) -> bool:
    requested_workers = max_workers
    current_workers = settings.get("max_workers")
    if requested_workers is not None and requested_workers != current_workers:
        return True
    return bool(settings.get("isolated", True) != isolated)


def _create_subinterpreter_executor(
    *, max_workers: int | None, isolated: bool
) -> Executor:
    try:
        return SubInterpreterExecutor(max_workers=max_workers, isolated=isolated)
    except SubInterpreterUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - unexpected failures
        raise SubInterpreterUnavailable(str(exc)) from exc


def _store_executor(
    executor: Executor,
    *,
    max_workers: int | None,
    isolated: bool,
) -> None:
    global _INTERPRETER_EXECUTOR, _EXECUTOR_SETTINGS
    _INTERPRETER_EXECUTOR = executor
    _EXECUTOR_SETTINGS = {"max_workers": max_workers, "isolated": isolated}


def _warn_subinterpreter_fallback(message: str) -> None:
    global _FALLBACK_WARNED
    if _FALLBACK_WARNED:
        return
    warnings.warn(message, RuntimeWarning, stacklevel=2)
    _FALLBACK_WARNED = True


def _register_atexit() -> None:
    global _ATEEXIT_REGISTERED
    if _ATEEXIT_REGISTERED:
        return
    atexit.register(reset_interpreter_executor)
    _ATEEXIT_REGISTERED = True
