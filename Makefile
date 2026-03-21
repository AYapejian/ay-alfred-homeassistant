.PHONY: lint format typecheck test build clean dev-install

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

format-check:
	uv run ruff format --check src/ tests/

typecheck:
	uv run mypy

test:
	uv run pytest tests/

build: clean
	./scripts/build.sh

dev-install:
	./scripts/dev-install.sh

clean:
	rm -rf dist/
