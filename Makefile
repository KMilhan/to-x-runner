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
		echo "==> pytest under $$py"; \
		uv run --python $$py pytest || exit $$?; \
	done

mutation:
	uv run mutmut run

mutation-results:
	uv run mutmut results
