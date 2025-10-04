lint-check:
	uv run ruff check .
	uv run ty check .

lint-fix:
	uv run ruff check . --fix --unsafe-fixes

mutation:
	uv run mutmut run

mutation-results:
	uv run mutmut results
