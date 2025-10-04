# Repository Guidelines

## Golden Rule
Every interface, document, and helper must describe concurrency in the language
Python developers already know from the standard library (`concurrent.futures`,
`asyncio`, `multiprocessing`). We are not inventing a new concurrency model—just
enhancing stdlib ergonomics. Avoid new nouns or surface syntax when threads,
processes, sub-interpreters, or free-threaded runtimes can be expressed with
existing terminology.

## Project Structure & Module Organization
Core logic lives in `src/unirun/`: `runtime.py` manages executor selection, `capabilities.py` captures interpreter traits, and `workloads.py` supplies deterministic helpers. The optional CLI wrapper is in `src/unirun_bench/` (`__main__.py`, `cli.py`) so it can ship independently. Tests reside in `tests/` with discovery driven by pytest; reuse the existing `test_unirun.py` layout when extending coverage. Packaging metadata and Hatch build targets stay in `pyproject.toml`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate`: bootstrap an isolated environment.
- `pip install -e .[benchmark]`: editable install plus optional benchmarks extras.
- `pytest`: run the full regression suite (pytest auto-discovers unittest cases too).
- `python -m unittest discover -s tests`: legacy command for parity while migrating.
- `hatch build` / `hatch publish`: produce and release artifacts after tagging.
- `python -m unirun_bench --profile all --samples 5 --json`: optional benchmark sweep for manual verification.

## Coding Style & Naming Conventions
Follow PEP 8 defaults: 4-space indentation, soft wrap near 100 characters, module-level constants in UPPER_SNAKE_CASE. Public APIs must expose explicit type hints (Literal unions, Protocols) that reuse standard-library names. Keep docstrings concise and situational, prefer `snake_case` for functions, and reserve `PascalCase` for dataclasses or capability records. When extending executors, keep thread names aligned with the `unirun-*` prefix so logs remain searchable. Anchor surface names and docstrings in standard-library vocabulary (`Executor`, `Future`, `to_thread`); call out when behavior is a drop-in replacement with optional enhancements.
As an agent, you keep the ratio of comment to code, 30 to 70. Follow Google Python Style Guide for docstrings and comments, keep EN-us spelling.

## Testing Guidelines
Prefer pytest with function-only tests (`test_<feature>`) under `tests/`. Use fixtures for setup instead of classes; when touching executor state, call `reset_state()` in a fixture or `finally` block. Reuse workloads from `unirun.workloads` to maintain deterministic timing and cover both auto and forced executor modes. Existing unittest-based suites continue to run via pytest—adapt or replace them incrementally.

Organize the suite so that each test module covers exactly one concurrency or parallelism feature. Companion parity checks with the CPython stdlib belong in files that share the feature name and end with `_double.py` (for example, `test_thread_executor.py` and `test_thread_executor_double.py`).

## Commit & Pull Request Guidelines
- Pull request titles can be as descriptive as needed; no enforced character limit.
- Commit subjects must begin with a gitmoji shortcode (e.g., `:sparkles:`) and may not use raw Unicode emojis or shorthand such as `:feat`. Follow the gitmoji with a single space and an imperative summary (e.g., `:sparkles: add interpreter executor docs`).
- Reference related issues in the body, including reproduction or benchmark notes when concurrency paths change.
- Pull requests should summarize user-facing impact, list test commands executed (include `pytest` runs), and attach before/after numbers for performance tweaks. Add screenshots or JSON excerpts only when the CLI output changes to preserve review context.

## Benchmark & Performance Notes
`unirun_bench` is optional but ideal for stress-testing new heuristics. Run the command above after altering executor defaults and share key JSON metrics in PR discussions. Avoid adding runtime dependencies; if a benchmark needs extras, guard imports so the core package stays dependency-free.
