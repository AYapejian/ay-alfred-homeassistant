.PHONY: lint format typecheck test build clean dev-install \
	demo-ha-up demo-ha-down demo-ha-reset demo-ha-token demo-ha-status

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

# Throwaway demo Home Assistant on 127.0.0.1:8124 (see demo/README.md)
demo-ha-up:
	./scripts/demo-ha.sh up

demo-ha-down:
	./scripts/demo-ha.sh down

demo-ha-reset:
	./scripts/demo-ha.sh reset

demo-ha-token:
	./scripts/demo-ha.sh token

demo-ha-status:
	./scripts/demo-ha.sh status
