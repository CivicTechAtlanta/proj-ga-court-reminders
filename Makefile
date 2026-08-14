.PHONY: setup run lint format requirements db-up db-down db-reset db-psql db-verify

setup:
	uv sync

synth:
	cdk synth

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
