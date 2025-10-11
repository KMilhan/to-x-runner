# Compat Migration Guide

This guide walks teams through replacing direct imports of `concurrent.futures`
and `asyncio` helpers with `unirun.compat` mirrors. The compat layer keeps the
stdlib surface intact while layering on capability-aware defaults, downgrade
warnings, and a clear path toward managed execution with `Run`.

## 1. Stage the rollout

1. **Snapshot behaviour** – Run your existing suite under the stdlib to capture
   baseline timings and functional results. Keep contract tests handy (for
   example the workloads in `unirun.workloads`) so you can re-run them once
   compat is enabled.
2. **Enable passthrough mode** – Set `UNIRUN_COMPAT_MODE=passthrough` in CI and
   staging. The compat modules will simply re-export the stdlib while the new
   package is installed, giving you a no-op deployment to prove packaging and
   import adjustments.

```bash
# Example staging configuration
export UNIRUN_COMPAT_MODE=passthrough
uv run pytest tests/
```

## 2. Swap imports without changing call sites

Replace stdlib imports with the matching compat module. All names exported by
compat mirror the stdlib spelling, so the rest of the file keeps working.

```diff
-from concurrent import futures
+from unirun.compat.concurrent import futures

-import asyncio
+from unirun.compat import asyncio
```

> Compat always returns real stdlib `Executor` objects and coroutine helpers, so
> annotated types and downstream APIs remain valid.

## 3. Opt in to managed behaviour

With imports updated, flip compat into managed mode and repeat the same tests.
Compat now routes through the `unirun` scheduler, applying deterministic worker
selection and instrumented fallbacks.

```bash
export UNIRUN_COMPAT_MODE=managed
uv run pytest tests/
```

### Downgrade signalling

Compat issues `RuntimeWarning` whenever behaviour deviates from the managed
path. Typical triggers include:

- Passing `initializer` or `mp_context` to an executor.
- Scheduler fallbacks (for example when sub-interpreters are unavailable and the
  request resolves to a thread pool).

Surface these warnings during local runs (`PYTHONWARNINGS=default`) or wire them
into logging/alerting. They act as guardrails so a rollout cannot silently
revert to stdlib semantics.

## 4. Tune thread behaviour

Compat honours the same thread-mode controls as `Run`. Set the environment
variable or pass an explicit `RuntimeConfig` when you are ready to compare GIL
and nogil behaviour.

| Setting | Effect |
| --- | --- |
| `UNIRUN_THREAD_MODE=auto` | Default heuristics pick either GIL or nogil pools based on interpreter capabilities. |
| `UNIRUN_THREAD_MODE=gil` | Force classic GIL-constrained thread pools even on free-threaded builds. |
| `UNIRUN_THREAD_MODE=nogil` | Prefer nogil thread executors when the interpreter supports parallel threads. |

You can also reuse compat in tandem with `Run` if a scope needs explicit
management:

```python
from unirun import Run
from unirun.compat.concurrent import futures

with Run(flavor="threads") as executor:
    futures.wait([executor.submit(fn) for fn in workloads])
```

## 5. Keep parity in sync

- Run `scripts/update_compat_parity.py` whenever new Python releases update the
  stdlib signature. This script re-generates `tests/data/compat_parity.json`
  which is enforced by `tests/test_compat_parity.py`.
- Execute `uv run pytest tests/test_compat_futures.py` to confirm the downgrade
  warnings stay covered and that managed pools still return correct results.

## 6. Document and monitor

- Add a brief entry to your service README describing the compat toggle and the
  warnings to watch.
- Capture dashboard alerts or log scrapes for `RuntimeWarning: *downgraded to
  stdlib behaviour*` so operators can respond quickly.
- When ready, follow the `Run` adoption guidance to move from compat parity to
  fully managed execution scopes with trace hooks.

---

If you encounter a downgrade warning that needs additional context, file an
issue with the message and a minimal reproducer. The compat layer is designed to
mirror stdlib semantics first, so unexpected fallbacks should be rare and
actionable.
