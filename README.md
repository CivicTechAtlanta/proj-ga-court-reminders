# GA Court Reminders

Lambda functions that find upcoming court hearings and send SMS reminders.

## Local development and testing

The local stack uses free tooling to run AWS Lambda emulation. It does not
require an AWS account or AWS credentials.

### 1. Prerequisites

#### Tools required on every platform

- [Git](https://git-scm.com/downloads)
- GNU Make, available as `make` through Xcode Command Line Tools on macOS (should already be available) or
  your Linux package manager
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js](https://nodejs.org/en/download) 22 or 24 LTS (or use a version manager like [mise](https://mise.jdx.dev/))
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html), installed after Node.js:

```bash
npm install --global aws-cdk
```

The project also needs three container components: the `docker` command, the
`docker compose` subcommand, and a running container engine. Choose the setup
for your operating system below. You do not need both Docker Desktop and Colima.

#### Linux container setup

The standard path assumes a distribution supported by Docker Engine, normally
Ubuntu (or Ubuntu-based like [Pop!_OS](https://system76.com/pop)), Debian, Fedora, RHEL, or CentOS.
The `systemctl` command below applies to systemd-based distributions.
Use your distribution's service manager otherwise.

Choose one option:

- **Docker Engine:** This is the standard Linux option. Follow the
  [installation guide](https://docs.docker.com/engine/install/) for your Linux
  distribution and install the
  [Compose plugin](https://docs.docker.com/compose/install/linux/). Start the
  service if the installer did not start it automatically:

```bash
sudo systemctl enable --now docker
```

- **Docker Desktop:** Install
  [Docker Desktop for Linux](https://docs.docker.com/desktop/setup/install/linux/)
  if you prefer a GUI. It includes the Docker CLI, Compose, and container engine,
  but currently requires x86-64 Linux, systemd, and KVM virtualization.

The project Makefile runs Docker without `sudo`. Docker Engine users whose
account cannot access Docker should follow Docker's
[Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)
and then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

Membership in the `docker` group grants root-level access. Rootless Docker and
other non-default daemon sockets are not currently verified.

The project currently uses Lambda's default x86-64 architecture. ARM64 Linux
hosts may require x86-64 container emulation and are not yet verified.

#### macOS container setup

These instructions support both Intel and Apple silicon. Colima requires macOS
13 or newer; Docker Desktop users should confirm the supported macOS versions
on its linked installation page.

Choose one option:

- **Docker Desktop:** This is the simplest GUI-based option for a new developer.
  Install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/),
  open the application, and wait until it reports that Docker is running. It
  includes the Docker CLI, Compose, and container engine.
- **Colima:** This is a lightweight command-line alternative to Docker Desktop.
  Install [Homebrew](https://brew.sh/) first, then run:

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker/cli-plugins
ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" \
  ~/.docker/cli-plugins/docker-compose
colima start
```

Colima must be running while developing. Start it with `colima start` and stop
it later with `colima stop`.

#### Windows and WSL2 support

Native Windows development through PowerShell or Command Prompt is not
supported. WSL2 with Docker Desktop should be viable when used as a Linux
development environment, but it is currently untested. Install the required
tools inside WSL, clone the repository in the WSL filesystem rather than under
`/mnt/c`, and run all project commands from the WSL terminal. The project team
may not be able to troubleshoot Windows-specific setup issues during meetups.

#### Optional database viewer

A database GUI is not required. [DBeaver Community](https://dbeaver.io/download/)
is a free option, but any PostgreSQL-compatible GUI will work. To inspect the
database without installing a GUI or PostgreSQL locally, use `make db-psql` to
open the `psql` command-line client inside the running database container.

### Verify the installation

Each command must complete without an error before continuing:

```bash
docker version
docker compose version
docker run --rm hello-world
```

Installation and the first local startup require internet access to GitHub,
package registries, and public container-image registries.

### 2. Clone, start, and test

Clone the repository, enter its directory, and start the local Lambda
environment:

```bash
git clone https://github.com/CivicTechAtlanta/proj-ga-court-reminders.git
cd proj-ga-court-reminders
make local-start
```

This one command verifies the required tools, installs project dependencies,
starts and bootstraps Floci, and deploys the CDK-managed Lambda functions using
dummy credentials. Start the optional fixture database separately with
`make db-up` when a Lambda needs court data.

### 3. Develop Lambda functions

The CDK-managed Lambda entry points are under `lambda/`:

- `main.py`
- `message_sender.py`
- `message_response.py`
- `message_status.py`

After changing Lambda code, redeploy it to Floci and invoke it by its CDK
construct name:

```bash
make local-deploy
make local-invoke FUNCTION=CourtBotMain EVENT=scripts/events/hello-api.json
```

The invocation response and any function error are printed in the current
terminal.

`EVENT` is optional for Lambdas that accept an empty event. For example:

```bash
make local-invoke FUNCTION=CourtBotMessageStatus
make local-invoke FUNCTION=CourtBotMessageResponse EVENT=path/to/event.json
```

#### Add a new Lambda

Add the handler under `lambda/`, register a `PythonFunction` with a unique CDK
construct name in `cdk_stack/cdk_stack.py`, and add a sample event under
`scripts/events/` when needed. Deploy the new infrastructure and invoke the
function:

```bash
make local-reset
make local-invoke FUNCTION=YourConstructName EVENT=scripts/events/your-event.json
```

No Lambda-specific Make target is required. `local-invoke` calls the Lambda
directly; it does not exercise an SQS queue, event-source mapping, retries, or a
DLQ. A future SQS workflow will need a separate enqueue command.

`make local-deploy` uses CDK hotswap because Floci cannot reliably update every
CloudFormation resource in place. After changing CDK infrastructure, use
`make local-reset` for a clean full deployment instead.

Useful database and project commands:

```bash
make db-verify     # run the seven-day hearing query; expect 11 rows
make db-psql       # open a psql shell
make help          # list annotated Make targets
```

For DBeaver or another PostgreSQL-compatible GUI, the fixture database is at
`postgresql://court:court@localhost:5434/courtdb`. Its dates are anchored when
the volume is first created. Run `make db-reset` to re-anchor the fixtures if
they age out.

Postgres translates the expected Benchmark/Odyssey SQL Server schema for local
development; it is not engine-compatible with SQL Server. See
[ADR 002](docs/adr/002-docker-postgres-simulates-court-case-db.md).

### 4. Stop or reset

Stop only this project's containers while preserving local data:

```bash
make local-down
```

This is the same on macOS and Linux. You may separately stop Docker Desktop or
Colima, but that also affects other projects using that runtime.

Delete all local data, rebuild the services, and redeploy the stack:

```bash
make local-reset
```

## AWS/CDK Deployment Process

Merges to this repo's `main` branch, will deploy through the repository pipeline. Manual deployment to a
real AWS account requires the AWS CLI and configured AWS credentials. Do not set
`AWS_ENDPOINT_URL` when targeting a real AWS account; the local Make targets set
it only for Floci.

Add project dependencies with `uv add <dependency>`, then run
`make requirements` to refresh the exported deployment requirements.

### Load the AWS dev database

The RDS SQL Server instance from `CourtDatabaseStack` starts empty. Give it
the same schema and fixtures as the local Docker database:

```bash
make aws-db-load
```

This invokes the `CourtBotDatabaseLoader` Lambda, which runs inside the
database VPC (a laptop cannot reach the instance directly). It creates the
`courtdb` database if needed, then drops and reloads every court table from
the T-SQL under `lambda/court_db/seed/sqlserver/`, the native counterpart of
`db/init/`. Fixture dates anchor to the server's current date, so rerun it to
re-anchor them. The result reports row counts and the reminder-query count,
which should be 11 right after loading.
