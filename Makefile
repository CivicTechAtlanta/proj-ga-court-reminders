DEMO_DIR := choose-your-own-adventure-demo

.PHONY: setup run test lint requirements

setup:
	cd $(DEMO_DIR) && uv sync

run:
	cd $(DEMO_DIR) && uv run func start

test:
	cd $(DEMO_DIR) && uv run python -m pytest

lint:
	cd $(DEMO_DIR) && uv run ruff check .

requirements:
	cd $(DEMO_DIR) && uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
