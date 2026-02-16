.PHONY: setup run test test-twilio test-azure test-integration test-all lint requirements

setup:
	uv sync

run:
	uv run func start

test:
	uv run python -m pytest --ignore=tests/integration

test-twilio:
	uv run --group test-sms python -m pytest tests/integration -m integration_twilio -v

test-azure:
	uv run python -m pytest tests/integration -m integration_azure -v

test-integration:
	uv run --group test-sms python -m pytest tests/integration -v

test-all:
	uv run --group test-sms python -m pytest -v

lint:
	uv run ruff check .

requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
