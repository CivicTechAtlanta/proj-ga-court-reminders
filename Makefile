.PHONY: setup run lint format requirements db-up db-down db-reset db-psql db-verify
#.PHONY: setup run test test-twilio test-azure test-integration test-all lint format requirements

setup:
	uv sync

synth:
	cdk synth


# setup:
# 	uv sync
# 	cp azure_functions/local.settings.copythis.json azure_functions/local.settings.json

# run:
# 	cd azure_functions && uv run func start

# test:
# 	uv run python -m pytest --ignore=tests/integration

# test-twilio:
# 	uv run --group integration python -m pytest tests/integration/test_twilio_sms.py -v -rs -s

# test-azure:
# 	uv run python scripts/run_azure_tests.py

# test-integration:
# 	uv run --group integration python -m pytest tests/integration -v -rs -s

# test-all:
# 	uv run --group integration python -m pytest -v -rs -s

db-up:
	docker compose up --detach --wait db

db-down:
	docker compose down

# Destroys the data volume so the init scripts re-run,
# re-anchoring fixture dates to today
db-reset:
	docker compose down --volumes
	docker compose up --detach --wait db

db-psql:
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-verify:
	docker compose exec -T db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1' < db/queries/next_week_hearings.sql

lint:
	uv run ruff check .

format:
	uv run ruff format .

requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
