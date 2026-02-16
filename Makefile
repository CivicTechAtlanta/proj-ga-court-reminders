.PHONY: setup run test test-twilio test-azure test-integration test-all lint format requirements

setup:
	uv sync
	cp azure_functions/local.settings.copythis.json azure_functions/local.settings.json

run:
	cd azure_functions && uv run func start

test:
	uv run python -m pytest --ignore=tests/integration

test-twilio:
	uv run --group integration python -m pytest tests/integration/test_twilio_sms.py -v

test-azure:
	uv run python scripts/run_azure_tests.py

test-integration:
	uv run --group integration python -m pytest tests/integration -v

test-all:
	uv run --group integration python -m pytest -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
