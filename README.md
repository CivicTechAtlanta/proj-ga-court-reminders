# GA Court Reminders

Lambda functions that find upcoming court hearings and send SMS reminders.

Everything runs locally without an AWS account: the Lambdas run in
[Floci](https://floci.io), a free AWS emulator, against a Postgres database that
Floci hosts and seeds with realistic court fixtures. The same CDK code deploys
to real AWS with RDS SQL Server.

## Getting started

Follow these steps in order on a fresh machine. Steps 1 and 2 install tools;
step 4 starts everything with one command.

### Step 1: Install the tools (every platform)

| Tool | Install |
|---|---|
| [Git](https://git-scm.com/downloads) | package manager or installer |
| GNU Make | macOS: included with Xcode Command Line Tools (`xcode-select --install`). Linux: your package manager |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Python package manager; installs Python itself if needed |
| [Node.js](https://nodejs.org/en/download) 22 or 24 LTS | installer, or a version manager such as [mise](https://mise.jdx.dev/) |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | installer; used for deploying to real AWS (the local stack does not need it) |
| [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) | after Node.js, run the command below |

```bash
npm install --global aws-cdk
```

### Step 2: Install a container engine

The project needs the `docker` command, the `docker compose` subcommand, and a
running container engine. Pick one option for your operating system; you do
not need more than one.

#### macOS (Intel or Apple silicon)

- **Docker Desktop** (simplest): install
  [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/),
  open it, and wait until it reports that Docker is running.
- **Colima** (lightweight, command-line; needs macOS 13+): install
  [Homebrew](https://brew.sh/), then:

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" \
  ~/.docker/cli-plugins/docker-compose
colima start
```

  Colima must be running while you develop: `colima start` / `colima stop`.

#### Linux (Ubuntu, Pop!_OS, Debian, Fedora, RHEL, CentOS)

- **Docker Engine** (standard): follow the
  [installation guide](https://docs.docker.com/engine/install/) for your
  distribution and install the
  [Compose plugin](https://docs.docker.com/compose/install/linux/). Start the
  service if the installer did not:

```bash
sudo systemctl enable --now docker
```

  The Makefile runs Docker without `sudo`. If your account cannot access
  Docker, follow the
  [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/),
  then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

  Membership in the `docker` group grants root-level access. Rootless Docker
  and non-default daemon sockets are not verified.

- **Docker Desktop for Linux**: install
  [Docker Desktop](https://docs.docker.com/desktop/setup/install/linux/) if you
  prefer a GUI (requires x86-64, systemd, and KVM).

#### Windows

Native Windows (PowerShell, Command Prompt) is not supported. WSL2 with Docker
Desktop should work as a Linux environment but is untested: install every tool
inside WSL, clone the repository into the WSL filesystem (not under `/mnt/c`),
and run all commands from the WSL terminal. The team may not be able to
troubleshoot Windows-specific issues during meetups.

### Step 3: Check the installation

Each command must complete without an error:

```bash
docker version
docker compose version
docker run --rm hello-world
cdk --version
uv --version
```

The first start needs internet access to GitHub, package registries, and
public container-image registries.

### Step 4: Clone and start

```bash
git clone https://github.com/CivicTechAtlanta/proj-ga-court-reminders.git
cd proj-ga-court-reminders
make local-start
```

`make local-start` checks the tools (`make doctor`), installs the Python
dependencies, starts Floci, bootstraps it for CDK, and deploys both CDK stacks
with dummy credentials. The deploy creates a Postgres database inside Floci and
seeds it with the court fixtures. The first run takes a minute or two, mostly
building the Lambda bundles. It has worked when the output ends with:

```
CourtReminderStack.CourtDatabaseSeedHearings = 11
Local Lambdas are ready. Run: make local-invoke FUNCTION=CourtBotMain EVENT=scripts/events/hello-api.json
```

### Step 5: Try it

Invoke the main Lambda, which queries the database for hearings due for a
reminder and returns them as JSON (11 of them right after a start):

```bash
make local-invoke FUNCTION=CourtBotMain EVENT=scripts/events/hello-api.json
```

Run the canonical seven-day hearing query against the database (expect
`(11 rows)`):

```bash
make db-verify
```

Run the tests. The four Postgres integration tests run against the Floci
database; the SQL Server ones skip unless you point them at a SQL Server:

```bash
uv run pytest
```

Connect a GUI such as [DBeaver Community](https://dbeaver.io/download/) (any
PostgreSQL-compatible client works) using the URL that `make db-url` prints,
normally:

```
postgresql://court:court@localhost:7001/courtdb
```

The tables live in the `dbo` schema, mirroring the SQL Server layout. Or open a
`psql` shell in a throwaway container with `make db-psql`.

## Starting from zero

To throw away every piece of local state and rebuild as if you had just
cloned:

```bash
make local-reset
```

This stops Floci, removes the containers and volumes it created (the Lambda
bundles and the database), deletes Floci's own state, and then runs the whole
`make local-start` sequence again: tool checks, Floci, bootstrap, deploy, seed.
Use it whenever you change CDK infrastructure, when something looks stuck, or
when you want a clean demo. It ends with the same two lines as step 4.

To stop the project without deleting anything:

```bash
make local-down
```

This stops Floci and removes its helper containers but keeps the data volumes;
`make local-start` picks up where you left off. Stopping Docker Desktop or
Colima also works but affects every project using that engine.

If only the fixture dates have gone stale (they are anchored to the day the
database was seeded, and the seven-day query goes empty about a week later),
re-seed without rebuilding:

```bash
make db-reset
```

Under the hood, `make local-start` is `doctor` (tool checks), `local-up`
(start Floci), `setup` (`uv sync`), `local-bootstrap` (CDK bootstrap, once),
and `local-deploy` (CDK deploy); `make local-reset` wipes state first and then
runs the same five. Each is a Make target you can run on its own, and
`make synth` renders the CloudFormation templates without deploying.

## Day-to-day development

### Lambda functions

The CDK-managed entry points are under `lambda/`: `main.py`,
`message_sender.py`, `message_response.py`, `message_status.py`, and
`database_loader.py` (the seed). Database access goes through the
`lambda/court_db/` package, which reads its settings from environment
variables and works unchanged against Floci's Postgres locally and RDS SQL
Server in AWS.

After changing Lambda code, redeploy and invoke by CDK construct name:

```bash
make local-deploy
make local-invoke FUNCTION=CourtBotMain EVENT=scripts/events/hello-api.json
```

The response and any function error print in your terminal. `EVENT` is
optional for Lambdas that accept an empty event:

```bash
make local-invoke FUNCTION=CourtBotMessageStatus
```

`make local-deploy` uses CDK hotswap because Floci cannot reliably apply
CloudFormation updates in place. After changing CDK infrastructure (anything
under `cdk_stack/`), use `make local-reset` instead.

To add a Lambda: add the handler under `lambda/`, register it with a unique
construct name in `cdk_stack/cdk_stack.py`, add a sample event under
`scripts/events/` if it needs one, then `make local-reset` and invoke it.
`local-invoke` calls the function directly; it does not exercise SQS,
event-source mappings, retries, or a DLQ.

### Database

| Command | What it does |
|---|---|
| `make db-verify` | run the seven-day hearing query; expect 11 rows after a seed |
| `make db-psql` | open a `psql` shell against the database |
| `make db-url` | print the connection URL for DBeaver or another GUI |
| `make db-reset` | re-seed the database, re-anchoring the date-relative fixtures |

The local database is Postgres standing in for the production Benchmark/Odyssey
SQL Server schema; it is not engine-compatible with SQL Server, and all SQL
against it must leave identifiers unquoted. See
[ADR 002](docs/adr/002-docker-postgres-simulates-court-case-db.md). Locally the
Lambdas are built for your machine's CPU architecture (Floci runs them
natively); in AWS they use Lambda's default x86-64.

### Checks

```bash
uv run pytest      # unit tests, plus integration tests when the stack is up
make lint          # ruff check
make format        # ruff format
make help          # every Make target with a one-line description
```

## AWS deployment

Merges to `main` deploy through the repository's GitHub Actions pipeline.
Manual deployment needs the AWS CLI and configured credentials. Do not set
`AWS_ENDPOINT_URL` when targeting real AWS; the local Make targets set it only
for Floci.

The same two stacks deploy: `CourtDatabaseStack` becomes RDS SQL Server
Express in an isolated-subnet VPC with generated credentials in Secrets
Manager, and `CourtReminderStack` places the Lambdas in that VPC.

Add project dependencies with `uv add <dependency>`, then run
`make requirements` to refresh the exported deployment requirements.

### Seeding the deployed database

Both deployments seed their database during `cdk deploy`: RDS SQL Server
Express in AWS, RDS Postgres on Floci. `CourtReminderStack` runs the
`CourtBotDatabaseLoader` Lambda as a CloudFormation custom resource (the
pattern from AWS's
[Use AWS CDK to initialize Amazon RDS instances](https://aws.amazon.com/blogs/infrastructure-and-automation/use-aws-cdk-to-initialize-amazon-rds-instances/)),
because the instance is only reachable from inside its VPC. It drops and
reloads every court table from the scripts under `lambda/court_db/seed/`, one
directory per engine with row-for-row the same data.

The seed re-runs automatically when those scripts change. To re-anchor the
fixture dates without changing the scripts, run `make db-reset` locally, or in
AWS deploy with a new `reseed` value:

```bash
uv run cdk deploy CourtReminderStack -c reseed=$(date +%s)
```

The stack output `CourtDatabaseSeedHearings` reports the reminder-query row
count right after seeding, which should be 11.
