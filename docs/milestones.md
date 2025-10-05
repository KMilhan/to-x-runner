# unirun v1.0 Milestones

## Current Stage
- Value narrative, documentation structure, and architectural contracts centred on `Run` and `compat` are in place, but the library surface still reflects the previous helper set (`run()`, `get_executor`, hint flags).
- `RuntimeConfig.thread_mode` (and matching environment toggles) are documented yet unimplemented; `Run` itself does not exist in code, nor does the scheduler bridge required to honour the new signature.
- Compat scaffolding and CPython parity test harnesses are not wired up; verification relies on the existing pytest suite only.

## Next Best Step
- Implement the `Run` context manager (sync and async), `RuntimeConfig.thread_mode`, and environment toggles (`UNIRUN_THREAD_MODE`). Wire them into the scheduler so the documented behaviour is real, and add smoke tests exercising `flavor="threads"` across GIL vs nogil builds.

## Roadmap to v1.0
1. **Executor Surface Alignment** *(see ARCHITECTURE.md §Primary Surfaces)*
   - Replace `run()`/`get_executor()` entry points with `Run` in code, updating imports and re-export lists.
   - Ensure existing helpers (`thread_executor`, `process_executor`, `interpreter_executor`) delegate through the new scheduler pathway.
2. **Scheduler Enhancements** *(see ARCHITECTURE.md §Scheduler & Capabilities)*
   - Introduce capability-driven selection respecting `RuntimeConfig` overrides.
   - Support explicit thread modes (auto/gil/nogil) and maintain deterministic fallbacks when unsupported.
3. **Compat Layer Delivery** *(see ARCHITECTURE.md §Primary Surfaces — compat)*
   - Build `unirun.compat` packages that mirror stdlib modules, backed by the shared scheduler.
   - Add migration guardrails (env toggles, warnings) and document usage recipes.
   - Integrate CPython contract suites (`test.concurrent_futures`, `test.asyncio`, executor-specific tests) to prove drop-in parity, and capture any deviations as explicit waivers.
4. **Instrumentation & Observability** *(see ARCHITECTURE.md §Run — Scope Instrumentation)*
   - Implement decision traces accessible from `Run` scopes; expose worker counts and lifecycle metrics.
   - Provide structured logging hooks for production monitoring.
5. **Verification Upgrades** *(see ARCHITECTURE.md §Verification Strategy)*
   - Wire CPython parity suites (`test.concurrent_futures`, `test.asyncio`) into CI against the compat layer.
   - Add mutation/stress fixtures covering shutdown edges and mixed interpreter runs.
   - Establish record/replay or canary harness guidance for adopters.
6. **Release Readiness** *(see ARCHITECTURE.md §Developer Experience & Future Work)*
   - Finalise docs (README quick start, architecture, recipes) to match the implemented API.
   - Run full test matrices across supported interpreters (3.11–3.14, GIL and nogil variants).
   - Tag v1.0 after at least one RC burn-in with benchmarks captured.
