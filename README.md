# GA Court Reminders

Lambda functions that send SMS court date reminders.

## Running Locally

### Setup for Local Development
1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Install [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
3. Install aws cdk cli using npm (`npm install -g aws-cdk`)
4. Install dependencies (For details, see "setup" in repo top-level [`Makefile`](./Makefile)):
   ```bash
   make setup
   ```
5. Start up Floci emulator in a new terminal(may need to run as superuser): `docker run --rm --name floci -p 4566:4566 -v /var/run/docker.sock:/var/run/docker.sock floci/floci:latest` 
6. Set the aws cli env vars to point to floci: ```
	export AWS_ENDPOINT_URL=http://localhost:4566
	export AWS_ACCESS_KEY_ID=test
	export AWS_SECRET_ACCESS_KEY=test
	export AWS_DEFAULT_REGION=us-east-1
   ``` 
7. If running for the first time, run `uv run cdk bootstrap` then `uv run cdk deploy CourtReminderStack`
8. After any changes to the lambda code, deploy using `uv run cdk deploy CourtReminderStack`. You can also run it in watch mode to auto deploy: `uv run cdk watch`

### Invoke a lambda
1. Make sure the aws cli env vars are set for local dev: ```
	export AWS_ENDPOINT_URL=http://localhost:4566
	export AWS_ACCESS_KEY_ID=test
	export AWS_SECRET_ACCESS_KEY=test
	export AWS_DEFAULT_REGION=us-east-1
   ```
2. List the lambdas: `aws lambda list-functions`
3. Select a lambda to invoke and take note of its function arn or function name. 
4. Invoke it: ```
   aws lambda invoke \
    --function-name <Function name or ARN> \
    --cli-binary-format raw-in-base64-out \
    --payload '{ "path": "/bob" }' \
    response.json
   ```






### Local court database

A Docker Postgres simulates the production court case-management database
(Odyssey-style SQL Server) with the tables used by the reminder query. Fixtures
are seeded automatically the first time the database starts.

Prerequisite: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(or any `docker compose` v2+).

```bash
make db-up      # start Postgres (first run seeds schema + fixtures)
make db-verify  # run the reminder query; expect 11 rows
make db-psql    # open a psql shell
make db-down    # stop (data volume is kept)
make db-reset   # destroy data volume and re-seed
```

Connection string: `postgresql://court:court@localhost:5434/courtdb`
(overridable via `COURT_DB_*` vars in `.env`; see `.template.env`).

Fixture event dates are anchored to the date the database is first started, so
the "7 days out" reminder query matches immediately. One case has daily
hearings for two weeks, so results stay non-empty for about a week — after
that, run `make db-reset` to re-anchor the dates. See
[ADR 002](docs/adr/002-docker-postgres-simulates-court-case-db.md) for design
details.

## Adding a new dependency
```bash
uv add <dependency name>
```

