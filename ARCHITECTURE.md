# Architecture Overview

## Value Pillars
- **Explicit scopes, predictable lifetimes** (`explicit is better than implicit`,
  Effective Python’s “use context managers for resources”): `Run` makes the
  concurrency choice and lifecycle visible in one place.
- **Readable migrations** (`readability counts`, “prefer helper functions that
  clarify intent”): `flavor` stays in stdlib vocabulary (`threads`, `processes`,
  `interpreters`), and deeper tuning happens through explicit config objects.
- **One obvious mechanism** (`there should be one— and preferably only one —obvious way to do it`):
  `Run` is the managed execution gateway; compat keeps drop-in parity without
  fragmenting entry points.
- **Progressively better defaults** (“make it easy to do the right thing”):
  scopes return real stdlib executors while layering deterministic teardown,
  capability-aware sizing, and instrumentation hooks.
- **Guided evolution** (Effective Python’s “write helper functions that clarify
  behavior” and “refactor acceptably by staging changes”): compat is the bridge,
  `Run` is the next step with structured contexts and optional config hooks.

## Guarantees
1. `Run` always returns a stdlib executor, so downstream APIs stay unchanged.
2. Scopes are explicit—both sync and async contexts expose lifecycle boundaries.
3. Flavors are explicit and limited to stdlib vocabulary, with optional config
   objects for teams that need to override defaults.
4. Instrumentation and fallbacks surface through simple attributes or callbacks so teams can observe decisions.

## Design Intent
- Golden rule: every public affordance must read like a standard-library API so Python developers can steer concurrency without new jargon, even as processes, threads, async, and free-threaded interpreters converge.
- Deliver drop-in helpers that mirror `concurrent.futures`, `asyncio`, and `multiprocessing` vocabulary while unifying setup and teardown behind the scenes.
- Provide clear, separate entry points for threads, processes, sub-interpreters, and cooperative async bridging without inventing naming schemes beyond what the stdlib already exposes.
- Offer an "automatic" scheduler that chooses a sensible backend using interpreter capabilities, yet remains opt-in, transparent, and expressed in terms of familiar `Executor` objects.
- Keep runtime dependencies at zero and ensure all heavy resources can be torn down deterministically for tests.

## Primary Surfaces

### Run
- Unified synchronous and asynchronous context manager exposing
  `__enter__`/`__exit__` plus `__aenter__`/`__aexit__`; inside every scope lives a
  real `concurrent.futures.Executor`.
- `flavor="auto"` mirrors the shared scheduler heuristics while explicit values
  (`"threads"`, `"processes"`, `"interpreters"`, `"none"`) pin the strategy without
  changing downstream call patterns.
- Optional `RuntimeConfig` objects can be passed for advanced tuning, keeping
  `Run` a router over shared scheduler logic instead of a bespoke executor type.
- Scope-level instrumentation (decision traces, worker counts, lifecycle
  metrics) hangs off the context instance, helping teams observe heuristics in
  production.
- Nested scopes detect re-entry and reuse compatible executors to minimise
  thrash while preserving isolation when flavors differ.
- Deterministic shutdown happens on scope exit unless the caller injects an
  existing executor—matching `ThreadPoolExecutor` context semantics.
- Async callers receive the same executor object and pair it with
  `loop.run_in_executor`, `asyncio.to_thread`, or compat helpers, so cooperative
  code retains familiar ergonomics while gaining tuned pools.

#### Signature Sketch

```python
class Run:
    def __init__(
        self,
        *,
        flavor: Literal["auto", "threads", "processes", "interpreters", "none"] = "auto",
        executor: Executor | None = None,
        max_workers: int | None = None,
        name: str | None = None,
        config: RuntimeConfig | None = None,
        trace: DecisionTrace | bool | None = None,
    ) -> None: ...

    def __enter__(self) -> Executor: ...
    def __exit__(self, exc_type, exc, tb) -> bool: ...
    async def __aenter__(self) -> Executor: ...
    async def __aexit__(self, exc_type, exc, tb) -> bool: ...
```

- `executor` lets callers supply an existing pool; when provided we skip managed
  shutdown unless `trace` requests instrumentation.
- `max_workers` and `name` are forwarded to the scheduler/config layer; absent
  values let capability-based defaults apply.
- `config` accepts a `RuntimeConfig` object for teams that need deterministic
  overrides (e.g., fixed pool sizes, disabled capability detection) without
  adding ad-hoc hints.
- `trace` either enables structured decision logging or accepts a callback that
  receives reason codes and pool metadata.
- `Literal`, `Executor`, `RuntimeConfig`, and `DecisionTrace` come from `typing`,
  `concurrent.futures`, and the scheduler module respectively; no new
  abstraction is introduced.

#### Usage Sketches

```python
from unirun import Run

# Synchronous scope choosing thread pools for IO-heavy work
with Run(flavor="threads", name="consumer") as executor:
    for payload in queue:
        executor.submit(process_payload, payload)

# Asynchronous scope that still returns a stdlib executor
async def refresh_cache(keys: list[str]) -> None:
    async with Run(flavor="auto") as executor:
        loop = asyncio.get_running_loop()
        await asyncio.gather(
            *(loop.run_in_executor(executor, compute_key, key) for key in keys)
        )
```

### compat
- Lives under `unirun.compat` and mirrors `concurrent.futures`/`asyncio`
  imports so teams can swap modules without touching call sites.
- Resolver functions delegate to the same scheduler used by `Run`, ensuring
  capability-aware sizing and fallbacks remain consistent across surfaces.
- Constructors, context managers, and helper coroutines keep stdlib signatures
  and return real `Future` objects; enhancements stay opt-in via environment
  toggles or explicit config objects.
- Escape hatches let teams pin pure stdlib behavior when required, keeping
  rollouts reversible.
- Documentation and recipes highlight one-to-one mappings (`ThreadPoolExecutor`,
  `as_completed`, `asyncio.to_thread`) so compat is understood as a swap-in, not
  a new abstraction.
- Compat modules live under `unirun.compat.concurrent.futures` and
  `unirun.compat.asyncio`, exposing stdlib-shaped APIs that delegate to the
  shared scheduler unless `UNIRUN_COMPAT_MODE=passthrough` reverts to the
  original implementations.

## Observability Hooks
- `Run(..., trace=...)` accepts booleans, `DecisionTrace` sinks, or callbacks so
  scopes can capture decisions without reaching into the scheduler directly.
- Global helpers (`add_decision_listener`, `remove_decision_listener`) let
  services register shared instrumentation regardless of whether they use
  `Run` or compat imports.
- The `observe_decisions()` context manager streams decisions to a logger,
  enabling structured logs/metrics during targeted rollouts.

## Components & Layout
- `src/unirun/api.py`: Houses the public helpers, including the `Run` context
  manager; keeps them as thin wrappers over executor factories so documentation
  can reference stdlib behaviors verbatim.
- `src/unirun/compat/`: Mirrors stdlib modules and re-exports helpers that point
  at managed executors, enabling `from unirun.compat import ThreadPoolExecutor`
  style drop-in replacements.
- `src/unirun/capabilities.py`: Detects Python version, GIL status, free-threaded flags, interpreter module availability, CPU topology, and suggested pool sizes.
- `src/unirun/scheduler.py`: Implements the automatic decision-making that powers `Run` and compat-facing helpers, using capability data plus optional `RuntimeConfig` overrides.
- `src/unirun/executors/threading.py`: Manages a singleton thread pool, worker naming, and graceful shutdown via `atexit`.
- `src/unirun/executors/process.py`: Wraps `ProcessPoolExecutor`, adding platform-specific safeguards (Windows spawn, fork warnings) while deferring to stdlib method names.
- `src/unirun/executors/subinterpreter.py`: Provides an executor abstraction over `interpreters.create()` / `run_string`, pooling interpreters when profitable and exposing only `Executor`-style methods.
- `src/unirun/executors/async_bridge.py`: Supplies `to_thread`, `to_process`, and `wrap_future` helpers that proxy to `asyncio` primitives so users never learn a new coroutine shape.
- `src/unirun/config.py`: Defines environment-variable overrides and a `RuntimeConfig` dataclass that both `Run` and compat-aware helpers consult for fine-tuning without changing the returned object type.
- `tests/`: Pytest suites, function-based, covering each executor path and the automatic scheduler.
- `examples/`: Optional recipes demonstrating swapping between the executors via standard `Executor` calls.

## Sub-Interpreter Strategy
- Use the `interpreters` module (available in CPython 3.12+) when present. For 3.13 builds requiring `-X gil=0`, spawn helper processes with the flag to host sub-interpreters; for 3.14+ native free-threaded interpreters, default to standard sub-interpreter calls.
- Maintain a pool of interpreter contexts keyed by module import mode (`isolated` vs shared). Each context pre-imports lightweight modules and exposes a queue-based request channel.
- Provide graceful fallback to thread execution when the `interpreters` module is unavailable, emitting a warning for clarity.

## Scheduler & Capabilities
- Inspect `capabilities.RuntimeCapabilities` on first use; cache results until `reset()` is invoked so executor selection remains predictable.
- When `flavor="auto"`, select the backend based on interpreter capabilities,
  environment policy, and optional `RuntimeConfig` overrides—no call-site hints
  are required.
- Allow environment overrides (`UNIRUN_FORCE_PROCESS=1`, `UNIRUN_FORCE_THREADS=1`) and `RuntimeConfig` settings to keep rollouts reversible and reproducible.
- Keep the heuristics explainable: record reason codes for each decision and expose them through lightweight introspection (e.g., `decision.trace()` or structured logging callbacks) so developers can see why a backend was chosen.
- Honour explicit user input first—if callers pass an executor instance, a `max_workers`, or a `RuntimeConfig` override, the scheduler must respect it without second-guessing the preference.
- Offer a zero-heuristics escape hatch (e.g., `flavor="none"` or `RuntimeConfig(auto=False)`) so teams can pin behavior to a specific executor when predictability outweighs automation.

## Lifecycle & Reset
- `reset()` tears down all pools (threads, processes, sub-interpreters) and clears cached capabilities—used heavily in tests.
- Register `atexit` handlers to ensure interpreters and pools shut down cleanly during normal program termination without requiring callers to learn new shutdown hooks.

## Verification Strategy
- Pytest function suites with fixtures for resetting the scheduler and mocking capability detection.
- Integration tests that verify `interpreter_executor()` behavior on interpreters supporting PEP 554, guarded by markers so CI can skip when unavailable.
- Property-style tests (hypothesis optional) to confirm Futures returned by standard `Executor.submit` maintain identity and completion semantics across executors.
- Each test module focuses on a single concurrency or parallelism feature. Parity suites that compare behavior with the CPython stdlib live in sibling files named with the same feature plus a `_double.py` suffix.
- Mirror CPython reference suites by running the compat layer against upstream
  `test.concurrent_futures`, `test.asyncio`, and related modules to lock in
  contract-level parity.
- Stress test lifecycle edges through mutation and long-running workloads so
  branch coverage and double execution are backed by resilience checks (e.g.,
  shutdown mid-flight, interpreter feature flips).
- Stage record/replay or canary deployments that run production traffic through
  the compat surface ahead of full cut-over, supplying empirical proof for
  teams that "it must work" in real environments.

## Developer Experience Commitments
- Publish quick-reference tables that map `Run` flavors and `compat` imports to the closest standard-library analogue (e.g., `Run(flavor="threads")` ↔ `ThreadPoolExecutor`), reinforcing the golden rule at a glance; house them under `docs/quick-reference.md` so contributors know where to extend them.
- Maintain migration recipes that show before/after diffs for replacing raw `ThreadPoolExecutor`, `ProcessPoolExecutor`, or `asyncio.to_thread` usage with `unirun` helpers in representative scripts and services, collected in `docs/recipes/`.
- Pair each recipe with a second phase demonstrating how to move from compat
  imports to `Run(flavor=...)` so teams understand the incremental path.
- Ship comprehensive typing support, including Protocols or type aliases that line up with `concurrent.futures` abstractions, so static analyzers provide guidance without introducing new type names.
- Document debugging and observability hooks in stdlib terms—examples should highlight how to integrate `as_completed`, logging, and tracing around the managed executors and futures.
- Highlight runtime guardrails wherever fallbacks occur (e.g., sub-interpreters downgrading to threads) and explain emitted warnings so developers trust the system when capabilities shift under them.

## Future Work
- Evaluate providing Trio/curio adapters once the core synchronous API stabilises.
- Consider structured logging hooks (callbacks) to observe scheduling decisions in production environments.
- Investigate packaging sub-interpreter pools as a standalone executor to share with other libraries once the implementation matures.
