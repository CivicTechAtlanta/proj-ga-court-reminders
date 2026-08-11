.PHONY: setup run lint format requirements

setup:
	uv sync

synth:
	cdk synth

lint:
	uv run ruff check .

format:
	uv run ruff format .

requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
