# unirun

![Mutation survivability](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/KMilhan/unirun/main/badges/mutation-survivability.json)

`unirun` gives Python developers a standard-library-fluent interface for running
"everything-to-everything" workloads across CPython's evolving execution
models. The project's golden rule is simple: keep speaking in the vocabulary of
`concurrent.futures`, `asyncio`, and `multiprocessing` even as processes,
threads, sub-interpreters, and free-threaded builds converge. The helpers work
on CPython 3.11+, including the free-threaded builds slated for Python 3.14.

> “We’re rolling 3.14 across the fleet and need every service to prove it still behaves under both the classic GIL threads and the new nogil runtime.”

`Run(flavor="threads", config=RuntimeConfig(thread_mode="auto"))` keeps one code
path adaptive across interpreters. Teams toggle `thread_mode="gil"` or
`"nogil"` (or set `UNIRUN_THREAD_MODE`) during canary runs to compare behavior
explicitly, without rewriting call sites.

- **Explicit scopes, predictable lifetimes** (`explicit is better than implicit`, Effective Python’s “use context managers for resources”): `Run` makes the concurrency choice and lifecycle visible in one place. A developer sees `with Run(flavor="threads")` and knows exactly what resource is being managed and when it shuts down.
- **Readable migrations** (`readability counts`, “prefer helper functions that clarify intent”): the `flavor` knob speaks stdlib language (`threads`, `processes`, `interpreters`). Optional overrides flow through explicit config objects. There’s no mystery heuristics—callers opt into them.
- **One obvious mechanism** (`there should be one— and preferably only one —obvious way to do it`): instead of sprinkling `get_executor`, manual context managers, and custom teardown, `Run` is the single entry point for managed execution scopes. Compat stays the bridge; `Run` is where teams go when they’re ready for better ergonomics.
- **Progressively better defaults** (“make it easy to do the right thing”): inside the scope we keep returning real stdlib executors, but we give deterministic teardown, capability-aware sizing, and instrumentation hooks automatically. Devs get a safer version of what they already know, not a new abstraction.
- **Guided evolution** (Effective Python’s “write helper functions that clarify behavior” and “refactor acceptably by staging changes”): `Run` becomes the obvious next step after compat. Same imports, now with a structured context that can emit decision traces, support async or sync code, and honour explicit config when teams are ready.

From that value statement we can articulate some concrete guarantees:

1. `Run` always returns a stdlib executor, so adopting it never changes downstream APIs.
2. Scopes are explicit—both sync and async contexts show the lifecycle boundary.
3. Flavors stay explicit and grounded in stdlib terminology; deeper tuning uses config objects instead of ad-hoc hints.
4. Instrumentation and fallbacks are surfaced through simple attributes/callbacks so teams can see what’s happening.

## Features

- Golden rule baked in—every helper exposes familiar stdlib nouns (`Executor`,
  `Future`, `submit`, `map`) so teams can adopt new runtimes without relearning
  terminology.
- Capability detection that snapshots interpreter/GIL traits and suggests sane
  pool sizes.
- Managed executor factories (`thread_executor()`, `process_executor()`,
  `interpreter_executor()`) that return real `concurrent.futures.Executor`
  instances with lifecycle handled for you.
- Automatic scheduling via `Run(flavor="auto")` so call sites stay synchronous
  while the library picks an appropriate backend.
- Async bridging helpers `to_thread` / `to_process` that wrap existing
  `asyncio` patterns instead of inventing new coroutine types.
- Benchmark harness covering micro → macro scenarios without runtime
  dependencies, plus an optional `unirun_bench` CLI module for manual analysis.

## Drop-In Parity, Optional Upgrades

`unirun` wraps the standard library rather than replacing it. Every helper
returns a real `concurrent.futures.Executor` or mirrors an `asyncio`
coroutine signature, so existing call sites keep working unchanged. Swap in the
matching `unirun` helper only when you want tuned defaults or automatic
capability detection—the underlying objects and futures stay the same.

| Keep this stdlib call                     | Optional helper when you want a boost   | What changes when you upgrade            |
| ---------------------------------------- | ---------------------------------------- | ---------------------------------------- |
| `Executor.submit(...).result()`          | `Run(flavor="auto")` scope               | Capability-aware executor picked for you |
| `asyncio.to_thread(func, *args)`         | `to_thread(func, *args)`                 | Pool sizing adapts to nogil builds       |
| `executor.map(iterable)`                 | `thread_executor().map(iterable)`        | Shared pool with managed lifecycle       |
| `ThreadPoolExecutor()` context manager   | `thread_executor()` context manager      | Named pools plus deterministic teardown  |
| Manual executor switching (`if cpu: ...`) | `Run(flavor="auto")`                    | One scope; capabilities pick the backend |
| Sub-interpreter experimentation          | `interpreter_executor()`                 | Standard `Executor` surface with fallback |

The optional helpers still hand back stdlib objects—`thread_executor()` yields a
`ThreadPoolExecutor`, `to_thread` awaits the same values you would get from
`asyncio.to_thread`, and `run` simply orchestrates `submit`/`result()` on your
behalf. Opting in buys you:

- Capability snapshots that choose threads, processes, or interpreters without
  sprinkling feature flags through your code.
- Consistent executor naming (`unirun-*`), teardown, and reset hooks across
  services so long-running apps stay predictable.
- Guardrails for emerging runtimes: free-threaded builds use tuned thread
  pools, while unsupported modes fall back to safe stdlib defaults.
- Observability hooks: `Run(trace=...)` plus `observe_decisions()` log or
  capture scheduler choices without custom plumbing.

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
from unirun import Run
from unirun.workloads import count_primes

with Run(flavor="auto") as executor:
    result = executor.submit(count_primes, 250_000).result()
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

### Scoped execution with `Run`

```python
import asyncio

from unirun import Run
from unirun.workloads import simulate_blocking_io


with Run(flavor="threads", name="ingest") as executor:
    executor.submit(simulate_blocking_io, 0.02)


async def hydrate_cache(keys):
    async with Run(flavor="auto") as executor:
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *(loop.run_in_executor(executor, simulate_blocking_io, 0.01) for _ in keys)
        )
```

## Optional Benchmark CLI

The base library keeps runtime dependencies at zero. For manual benchmarking,
invoke the optional CLI module without affecting core installs:

## Real-World Usage Catalog

Explore a curated set of 60 real-world workloads where `unirun` keeps the
standard library vocabulary front and center while scaling across interpreters by
running the scripts in [`examples/`](examples/) or importing the structured
catalog documented in [`examples/README.md`](examples/README.md).

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

## Mutation Testing

Mutation testing enforces that behavior-focused assertions fail when
capabilities or workloads break. The project relies on the
`ensure-compatibility-with-python-3.14` fork of [`mutmut`](https://github.com/KMilhan/mutmut)
so experiments stay green on the Python 3.14 alphas.

```bash
# Install developer dependencies, including the patched mutmut fork
uv sync --group dev

# Run the mutation suite with the built-in pytest runner
uv run mutmut run

# Inspect surviving mutants directly in the terminal (optional)
uv run mutmut results

# Refresh the survivability badge after a mutation run
uv run python scripts/update_mutation_badge.py --skip-run
```

The `[tool.mutmut]` block in `pyproject.toml` keeps mutation runs inside the
`src/unirun` package while letting the CLI discover tests in `tests/`. This keeps
the suite aligned with the golden rule by mutating only the user-facing
concurrency helpers.

## Design Notes

- No runtime third-party dependencies. Native accelerators remain optional and
  can be added via C extensions that participate in the free-threaded ABI.
- The golden rule applies to code and docs alike: describe behaviors with the
  same nouns and verbs the Python stdlib already uses (`Executor`, `Future`,
  `submit`, `map`, `as_completed`).
- Capability detection relies solely on stdlib primitives so that behavior is
  stable across CPython releases and alternative builds (musl, manylinux, etc).

## Release Automation

Trigger the `Semantic Release with Girokmoji` workflow from the Actions tab to generate release notes and version tags automatically.

1. Launch the workflow manually and choose the semantic version segment to bump (`patch`, `minor`, or `major`).
2. The pipeline installs dependencies with `uv`, executes `uv run pytest`, and then invokes `girokmoji` to create a changelog (`release.md`).
3. Successful runs push the updated tag back to the repository, upload the changelog as an artifact, and publish a GitHub Release using the generated notes.

This workflow mirrors the reference pipeline in [girokmoji](https://github.com/KMilhan/girokmoji) so future tooling updates stay compatible with our release process.
