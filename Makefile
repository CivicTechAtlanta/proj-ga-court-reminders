.DEFAULT_GOAL := help

.PHONY: help setup synth db-url db-psql db-verify db-reset lint format \
	requirements doctor local-up local-deploy local-start local-invoke \
	local-bootstrap local-down local-reset

## List the supported development commands
help:
	@awk '/^## / {description = substr($$0, 4); getline; split($$0, target, ":"); printf "  %-18s %s\n", target[1], description}' $(MAKEFILE_LIST)

## Install project dependencies with uv
setup:
	uv sync

## Synthesize the CDK stack without deploying it
synth:
	uv run cdk synth

## Print the connection URL of the court database running in Floci (DBeaver, psql)
db-url:
	@$(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_db_url.py

## Open a psql shell against the court database running in Floci
db-psql:
	docker run --rm -it --network court-reminders_default postgres:16-alpine \
		psql "$$($(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_db_url.py --docker-network)"

## Run the seven-day fixture query; expect 11 rows right after a seed
db-verify:
	docker run --rm -i --network court-reminders_default postgres:16-alpine \
		psql "$$($(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_db_url.py --docker-network)" \
		-v ON_ERROR_STOP=1 < db/queries/next_week_hearings.sql

## Re-seed the court database in Floci, re-anchoring the date-relative fixtures
db-reset:
	$(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_invoke.py CourtBotDatabaseLoader

## Run the repository Ruff checks
lint:
	uv run ruff check .

## Format repository Python files with Ruff
format:
	uv run ruff format .

## Export application dependencies to requirements.txt
requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt


# =============================================================================
# Local Lambda development (Docker + Floci)
# =============================================================================

FUNCTION ?= CourtBotMain
EVENT ?=
LOCAL_AWS_ENV := env AWS_ENDPOINT_URL=http://localhost:4566 \
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
	AWS_DEFAULT_REGION=us-east-1 AWS_REGION=us-east-1

## Verify tools shared by macOS and Linux local development.
doctor:
	@command -v git >/dev/null && echo "ok: git" || { echo "missing: git"; exit 1; }
	@command -v uv >/dev/null && echo "ok: uv" || { echo "missing: uv"; exit 1; }
	@command -v node >/dev/null || { echo "missing: Node.js"; exit 1; }; \
		node_major="$$(node -p 'process.versions.node.split(".")[0]')"; \
		case "$$node_major" in \
			22|24) echo "ok: Node $$(node --version)" ;; \
			*) echo "warning: Node $$(node --version); CDK supports Node 22 or 24 LTS" ;; \
		esac
	@command -v docker >/dev/null && echo "ok: docker CLI" || { echo "missing: docker CLI"; exit 1; }
	@docker compose version >/dev/null && echo "ok: docker compose" || { echo "missing: docker compose v2"; exit 1; }
	@docker compose up --help | grep -q -- '--wait' && echo "ok: docker compose supports --wait" || { echo "Docker Compose is too old; install a current Compose v2 release"; exit 1; }
	@docker info >/dev/null 2>&1 && echo "ok: Docker daemon" || { echo "Docker daemon unavailable. Start Docker Desktop, Docker Engine, or Colima."; exit 1; }
	@command -v cdk >/dev/null && echo "ok: AWS CDK CLI" || { echo "missing: AWS CDK CLI"; exit 1; }

## Start the local AWS emulator
local-up: doctor
	docker compose up --detach --wait floci

## Bootstrap Floci once; repeated CDK bootstraps are not emulator-safe
local-bootstrap:
	$(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_bootstrap.py

## Deploy the CDK stack to Floci
local-deploy: setup local-bootstrap
	$(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_cdk_deploy.py

## Start the full local stack and deploy the current Lambda code
local-start: local-up local-deploy
	@echo "Local Lambdas are ready. Run: make local-invoke FUNCTION=CourtBotMain EVENT=scripts/events/hello-api.json"

## Invoke any CDK Lambda by construct name; optionally set EVENT=path.json
local-invoke:
	$(LOCAL_AWS_ENV) uv run --with boto3==1.40.3 python scripts/local_invoke.py \
		"$(FUNCTION)" $(if $(EVENT),"$(EVENT)",)

## Stop this project's containers while preserving local data
local-down:
	docker compose stop floci
	uv run python scripts/local_cleanup.py
	docker compose down

## Delete local data, rebuild services, and redeploy the CDK stack
local-reset: doctor
	docker compose stop floci
	uv run python scripts/local_cleanup.py --volumes
	docker compose down --volumes --remove-orphans
	$(MAKE) local-start
