lint-check:
	uv run ruff check .
	uv run ty check .

lint-fix:
	uv run ruff check . --fix --unsafe-fixes

test:
	uv run pytest
