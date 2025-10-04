# unirun

`unirun` gives Python developers a standard-library-fluent interface for running
"everything-to-everything" workloads across CPython's evolving execution
models. The project's golden rule is simple: keep speaking in the vocabulary of
`concurrent.futures`, `asyncio`, and `multiprocessing` even as processes,
threads, sub-interpreters, and free-threaded builds converge. The helpers work
on CPython 3.11+, including the free-threaded builds slated for Python 3.14.

## Features

- Golden rule baked in—every helper exposes familiar stdlib nouns (`Executor`,
  `Future`, `submit`, `map`) so teams can adopt new runtimes without relearning
  terminology.
- Capability detection that snapshots interpreter/GIL traits and suggests sane
  pool sizes.
- Managed executor factories (`thread_executor()`, `process_executor()`,
  `interpreter_executor()`) that return real `concurrent.futures.Executor`
  instances with lifecycle handled for you.
- Automatic scheduling via `get_executor(mode="auto", **hints)` and `run(...)`
  so call sites stay synchronous while the library picks an appropriate backend.
- Async bridging helpers `to_thread` / `to_process` that wrap existing
  `asyncio` patterns instead of inventing new coroutine types.
- Benchmark harness covering micro → macro scenarios without runtime
  dependencies, plus an optional `unirun_bench` CLI module for manual analysis.

## Drop-In Parity, Optional Upgrades

Keep writing the stdlib code you already trust—`unirun` only steps in when you
want smoother ergonomics or smarter defaults.

| Stdlib pattern you keep using              | Optional `unirun` assist                                   | What improves when you opt in                                      |
| ----------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| `Executor.submit(...).result()`           | `run(..., cpu_bound=True)`                                 | Same synchronous call, plus capability-aware executor selection    |
| `asyncio.to_thread(func, *args)`          | `to_thread(func, *args)`                                   | Identical signature, auto-tuned pools on nogil builds              |
| `executor.map(iterable)`                  | `thread_executor().map(iterable)`                          | Familiar API, shared executor lifecycle handled for you            |
| `ThreadPoolExecutor()` context managers   | `thread_executor()` context manager                        | Drop-in replacement with deterministic teardown and reset hooks    |
| Manual executor switching (`if cpu: ...`) | `get_executor(mode="auto", **hints)`                      | One call site; capabilities decide whether threads/processes win   |
| Sub-interpreter experimentation           | `interpreter_executor()`                                    | Presents the standard `Executor` surface with safe thread fallback |

## Seamless `asyncio.to_thread` Upgrades

- The `to_thread` helper mirrors `asyncio.to_thread` exactly, so call sites need
  no signature or import changes during migration.
- Capability detection spots free-threaded (nogil) interpreters and routes work
  through a tuned `thread_executor()` that actually scales across cores, while
  falling back cleanly when nogil is unavailable.
- Decision traces and logging hooks let teams verify why the scheduler chose a
  particular executor—critical when rolling out nogil builds incrementally.

## Why This Still Matters on Python 3.14

- Executor management remains real work—`unirun` sizes and names shared pools, registers shutdown hooks, and keeps lifecycle consistent across services so teams can focus on business logic.
- Async bridges still need configuration—`to_thread` and friends delegate to tuned executors automatically instead of requiring manual loop-level overrides in every coroutine.
- Uniform APIs smooth mixed environments—even if production guarantees 3.14, local runs, tests, or downstream consumers may lag, so the same stdlib-shaped helpers behave correctly across interpreter versions without forks.

## Life Without `unirun`

- Teams hand-roll capability checks (`sysconfig.get_config_var("Py_GIL_DISABLED")`),
  scatter feature flags, and duplicate heuristics to guess pool sizes.
- Each service implements its own executor lifecycle: global singletons,
  `atexit` handlers, ad-hoc worker naming, and inconsistent shutdown semantics
  that often leak futures or swallow `CancelledError`.
- Tests require bespoke fixtures to reset global executors and mock capability
  detection, fragmenting coverage across GIL and nogil environments.
- Documentation drifts away from stdlib language as wrappers like `run_in_threads`
  or `bg_task` multiply, raising the onboarding cost for new contributors.

```python
# Typical DIY nogil helper without unirun
_FREE_THREAD = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
_GLOBAL_EXECUTOR: ThreadPoolExecutor | None = None

def get_executor() -> ThreadPoolExecutor:
    global _GLOBAL_EXECUTOR
    if _GLOBAL_EXECUTOR is None:
        max_workers = os.cpu_count() if _FREE_THREAD else (os.cpu_count() or 1) * 5
        _GLOBAL_EXECUTOR = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="app-nogil" if _FREE_THREAD else "app-gil",
        )
        atexit.register(_GLOBAL_EXECUTOR.shutdown)
    return _GLOBAL_EXECUTOR

async def to_thread(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    loop = asyncio.get_running_loop()
    executor = get_executor() if _FREE_THREAD else None
    return await loop.run_in_executor(executor, functools.partial(func, *args, **kwargs))
```

```python
# With unirun the same coroutine stays readable
from unirun import to_thread

async def main() -> None:
    await to_thread(func, *args, **kwargs)  # signature matches asyncio.to_thread
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Hatchling powers packaging with dynamic (VCS-based) SemVer tags so publishing to
PyPI only requires tagging:

```bash
hatch build
hatch publish
```

## Quick Start

### Automatic execution in one call

```python
from unirun import run
from unirun.workloads import count_primes

result = run(count_primes, 250_000, cpu_bound=True)
print(result)
```

### Manual control with a managed thread pool

```python
from unirun import thread_executor
from unirun.workloads import simulate_blocking_io

durations = [0.01, 0.02, 0.03]

with thread_executor() as executor:
    for value in executor.map(simulate_blocking_io, durations):
        print(value)
```

### Async bridging (drop-in parity with `asyncio.to_thread`)

```python
import asyncio

from unirun import to_thread
from unirun.workloads import simulate_blocking_io


async def main() -> None:
    await to_thread(simulate_blocking_io, 0.05)


asyncio.run(main())
```

## Optional Benchmark CLI

The base library keeps runtime dependencies at zero. For manual benchmarking,
invoke the optional CLI module without affecting core installs:

```bash
python -m unirun_bench --profile all --samples 5 --json
```

The CLI returns JSON (optionally annotated with capability snapshots) or prints
the formatted table generated by `unirun.benchmarks.format_table`.

## Testing & Coverage

The test suite follows Kent Beck's TDD ethos—covering sync, async, CPU, IO, and
process-path behaviors:

```bash
python -m unittest discover -s tests
```

Pytest modules are organized by feature: one test file per concurrency surface,
with matching `_double.py` companions to assert drop-in parity with the CPython
stdlib.

## Design Notes

- No runtime third-party dependencies. Native accelerators remain optional and
  can be added via C extensions that participate in the free-threaded ABI.
- The golden rule applies to code and docs alike: describe behaviors with the
  same nouns and verbs the Python stdlib already uses (`Executor`, `Future`,
  `submit`, `map`, `as_completed`).
- Capability detection relies solely on stdlib primitives so that behavior is
  stable across CPython releases and alternative builds (musl, manylinux, etc).
