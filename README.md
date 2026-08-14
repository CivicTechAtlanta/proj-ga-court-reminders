# GA Court Reminders

Lambda functions that send SMS court date reminders.

## Setting up AWS and CDK
1. Install [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
2. Install aws cdk cli using npm (`npm install -g aws-cdk`)
3. Make sure you're logged in to AWS. Configure login with aws cli (`aws login`). 


## Local Development
1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Install dependencies (For details, see "setup" in repo top-level [`Makefile`](./Makefile)):
   ```bash
   make setup
   ```
3. After CDK changes, run `cdk deploy`. If actively developing, run `cdk watch` in a different terminal


## Running Locally

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

