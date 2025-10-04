# Architecture Overview

## Design Intent
- Golden rule: every public affordance must read like a standard-library API so Python developers can steer concurrency without new jargon, even as processes, threads, async, and free-threaded interpreters converge.
- Deliver drop-in helpers that mirror `concurrent.futures`, `asyncio`, and `multiprocessing` vocabulary while unifying setup and teardown behind the scenes.
- Provide clear, separate entry points for threads, processes, sub-interpreters, and cooperative async bridging without inventing naming schemes beyond what the stdlib already exposes.
- Offer an "automatic" scheduler that chooses a sensible backend using interpreter capabilities, yet remains opt-in, transparent, and expressed in terms of familiar `Executor` objects.
- Keep runtime dependencies at zero and ensure all heavy resources can be torn down deterministically for tests.

## Public API Sketch
- `run(func, *args, **kwargs)`: Execute synchronously using the automatic scheduler (threads, processes, or sub-interpreters depending on capabilities and hints) and return the function result; mirrors `concurrent.futures.Executor.submit(...).result()` usage.
- `thread_executor(max_workers=None)`: Return a managed `ThreadPoolExecutor` configured with interpreter-aware defaults so callers can use `submit`, `map`, or `as_completed` exactly as in the stdlib.
- `process_executor(max_workers=None)`: Return a managed `ProcessPoolExecutor`, guarding platform quirks while leaving the API identical to the stdlib executor surface.
- `interpreter_executor(*, isolated=True)`: Expose a pool matching the `Executor` protocol that routes work through sub-interpreters when supported, falling back to threads with the same method names when unavailable.
- `get_executor(mode="auto", **hints)`: Provide an automatic chooser that returns one of the above executors; the object still conforms to `concurrent.futures.Executor` so downstream code does not change.
- `submit(executor, func, *args, **kwargs)`: Thin shim over `executor.submit` that exists solely for ergonomic parity with existing docs and typing helpers; no new behavior.
- `map(executor, func, iterable, *, timeout=None)`: Delegates to `executor.map` while allowing automatic executors to participate without new keywords.
- `to_thread(func, *args, **kwargs)` / `to_process(func, *args, **kwargs)`: Async helpers that behave like `asyncio.to_thread`, using the managed executors under the hood but keeping the cooperative language unchanged.
- `wrap_future(future)`: Forward compatibility helper that defers to `asyncio.wrap_future`; prevents projects from depending on custom awaitable types.

## Package Layout (Proposed)
- `src/unirun/api.py`: Houses the public helpers; keeps them as thin wrappers over executor factories so documentation can reference stdlib behaviors verbatim.
- `src/unirun/capabilities.py`: Detects Python version, GIL status, free-threaded flags, interpreter module availability, CPU topology, and suggested pool sizes.
- `src/unirun/scheduler.py`: Implements the automatic decision-making for `get_executor`, using capability data plus optional call-site hints (e.g., `io_bound=True`).
- `src/unirun/executors/threading.py`: Manages a singleton thread pool, worker naming, and graceful shutdown via `atexit`.
- `src/unirun/executors/process.py`: Wraps `ProcessPoolExecutor`, adding platform-specific safeguards (Windows spawn, fork warnings) while deferring to stdlib method names.
- `src/unirun/executors/subinterpreter.py`: Provides an executor abstraction over `interpreters.create()` / `run_string`, pooling interpreters when profitable and exposing only `Executor`-style methods.
- `src/unirun/executors/async_bridge.py`: Supplies `to_thread`, `to_process`, and `wrap_future` helpers that proxy to `asyncio` primitives so users never learn a new coroutine shape.
- `src/unirun/config.py`: Defines environment-variable overrides and a `RuntimeConfig` dataclass that users can pass to `get_executor` for fine-tuning without changing the returned object type.
- `tests/`: Pytest suites, function-based, covering each executor path and the automatic scheduler.
- `examples/`: Optional recipes demonstrating swapping between the executors via standard `Executor` calls.

## Sub-Interpreter Strategy
- Use the `interpreters` module (available in CPython 3.12+) when present. For 3.13 builds requiring `-X gil=0`, spawn helper processes with the flag to host sub-interpreters; for 3.14+ native free-threaded interpreters, default to standard sub-interpreter calls.
- Maintain a pool of interpreter contexts keyed by module import mode (`isolated` vs shared). Each context pre-imports lightweight modules and exposes a queue-based request channel.
- Provide graceful fallback to thread execution when the `interpreters` module is unavailable, emitting a warning for clarity.

## Automatic Scheduling Heuristics
- Inspect `capabilities.RuntimeCapabilities` on first use; cache results until `reset()` is invoked so executor selection remains predictable.
- For CPU-bound hints (`get_executor(mode="cpu")` or `run(..., cpu_bound=True)`), prefer processes unless free-threaded support is detected, in which case threads or sub-interpreters may be used.
- For IO-bound hints, prefer the thread pool; allow environment overrides (`UNIRUN_FORCE_PROCESS=1`) to handle pathological cases while still returning a familiar `Executor` instance.
- Provide declarative hints via keyword arguments (`cpu_bound`, `io_bound`, `prefers_subinterpreters`) instead of new decorator concepts, keeping the call signatures close to stdlib helpers.
- Keep the heuristics explainable: record reason codes for each decision and expose them through lightweight introspection (e.g., `decision.trace()` or structured logging callbacks) so developers can see why a backend was chosen.
- Honour explicit user input first—if callers pass an executor instance, a `max_workers`, or a `RuntimeConfig` override, the scheduler must respect it without second-guessing the preference.
- Offer a zero-heuristics escape hatch (e.g., `mode="none"` or `RuntimeConfig(auto=False)`) so teams can pin behavior to a specific executor when predictability outweighs automation.

## Lifecycle & Reset
- `reset()` tears down all pools (threads, processes, sub-interpreters) and clears cached capabilities—used heavily in tests.
- Register `atexit` handlers to ensure interpreters and pools shut down cleanly during normal program termination without requiring callers to learn new shutdown hooks.

## Testing Approach
- Pytest function suites with fixtures for resetting the scheduler and mocking capability detection.
- Integration tests that verify `interpreter_executor()` behavior on interpreters supporting PEP 554, guarded by markers so CI can skip when unavailable.
- Property-style tests (hypothesis optional) to confirm Futures returned by standard `Executor.submit` maintain identity and completion semantics across executors.
- Each test module focuses on a single concurrency or parallelism feature. Parity suites that compare behavior with the CPython stdlib live in sibling files named with the same feature plus a `_double.py` suffix.

## Developer Experience Commitments
- Publish quick-reference tables that map each `unirun` helper to the closest standard-library analogue (e.g., `run` ↔ `Executor.submit().result()`), reinforcing the golden rule at a glance; house them under `docs/quick-reference.md` so contributors know where to extend them.
- Maintain migration recipes that show before/after diffs for replacing raw `ThreadPoolExecutor`, `ProcessPoolExecutor`, or `asyncio.to_thread` usage with `unirun` helpers in representative scripts and services, collected in `docs/recipes/`.
- Ship comprehensive typing support, including Protocols or type aliases that line up with `concurrent.futures` abstractions, so static analyzers provide guidance without introducing new type names.
- Document debugging and observability hooks in stdlib terms—examples should highlight how to integrate `as_completed`, logging, and tracing around the managed executors and futures.
- Highlight runtime guardrails wherever fallbacks occur (e.g., sub-interpreters downgrading to threads) and explain emitted warnings so developers trust the system when capabilities shift under them.

## Future Work
- Evaluate providing Trio/curio adapters once the core synchronous API stabilises.
- Consider structured logging hooks (callbacks) to observe scheduling decisions in production environments.
- Investigate packaging sub-interpreter pools as a standalone executor to share with other libraries once the implementation matures.
