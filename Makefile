lint-check:
	uv run ruff check .
	uv run ty check . --exclude tests/.cpython-tests

lint-fix:
	uv run ruff check . --fix --unsafe-fixes

test:
	uv run pytest

COMPAT_PYTHONS ?= 3.11 3.12 3.13 3.14

test-compat:
	@for py in $(COMPAT_PYTHONS); do \
		echo "==> pytest under $$py"; \
		uv run --python $$py pytest || exit $$?; \
	done

contract-versions:
	@for py in $(COMPAT_PYTHONS); do \
		echo "==> contracts under $$py"; \
		uv run --python $$py pytest tests/test_cpython_contracts.py || exit $$?; \
	done

lock-fix:
	python scripts/ensure_uv_lock_version.py

lock-check:
	python scripts/ensure_uv_lock_version.py --check

mutation:
	uv run mutmut run

mutation-results:
	uv run mutmut results
