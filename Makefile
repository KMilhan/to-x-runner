lint-check:
	uv run ruff check .
	uv run ty check .

lint-fix:
	uv run ruff check . --fix --unsafe-fixes

test:
	uv run pytest

COMPAT_PYTHONS ?= 3.11 3.12 3.13

test-compat:
	@for py in $(COMPAT_PYTHONS); do \
		echo "==> installing project under $$py"; \
		uv pip install --python $$py . pytest || exit $$?; \
		echo "==> pytest under $$py"; \
		uv run --python $$py pytest || exit $$?; \
		echo "==> CPython contracts under $$py"; \
		uv run --python $$py pytest tests/compat/test_cpython_contracts.py || exit $$?; \
	done

mutation:
	uv run mutmut run

mutation-results:
	uv run mutmut results
