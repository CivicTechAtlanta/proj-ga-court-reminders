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
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Python package manager; installs Python itself if needed |
| [Node.js](https://nodejs.org/en/download) 22 or 24 LTS | installer, or a version manager such as [mise](https://mise.jdx.dev/) |
| [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | installer; used for deploying to real AWS (the local stack does not need it) |

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

  The scripts run Docker without `sudo`. If your account cannot access
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

### Step 3: Put your credentials in place (all routes need this)

```bash
cp .template.env .env
```

Open `.env` and fill in three values from your TrueDialog credentials email
and the TrueDialog portal:

| Variable | Where to find it |
|---|---|
| `TRUEDIALOG_API_KEY` | credentials email |
| `TRUEDIALOG_API_SECRET` | credentials email |
| `TRUEDIALOG_ACCOUNT_ID` | portal, beside the account name, top right |

Leave `TRUEDIALOG_CHANNEL_ID` at `22`. That is the account's default number.
`.env` is gitignored; see [Credentials and what never to
commit](#credentials-and-what-never-to-commit).


### Step 4: Clone and start

```bash
git clone https://github.com/CivicTechAtlanta/proj-ga-court-reminders.git
cd proj-ga-court-reminders
. script/setup
```

The first start needs internet access to GitHub, package registries, and
public container-image registries.


`. script/setup` checks the tools, installs the Python
dependencies, starts Floci, bootstraps it for CDK, and deploys both CDK stacks
with dummy credentials. The deploy creates a Postgres database inside Floci and
seeds it with the court fixtures. It will also verify the data in the database and TruDialog credentials. The first run takes a minute or two, mostly
building the Lambda bundles. It has worked when the output ends with something like:

```
CourtReminderStack.CourtDatabaseSeedHearings = 12
...
Local Lambdas are ready. Run: . script/run CourtBotMain script_helpers/events/hello-api.json
```

### Step 5: Try it

Invoke the main Lambda, which queries the database for hearings due for a
reminder and returns them as JSON (12 of them right after a start):

```bash
. script/run CourtBotMain scripts/events/hello-api.json
```

Run the tests. The Postgres integration tests run against the Floci
database; the SQL Server ones skip unless you point them at a SQL Server:

```bash
. script/test
```

Connect a GUI such as [DBeaver Community](https://dbeaver.io/download/) (any
PostgreSQL-compatible client works) using the URL that `. script/setup` prints,
normally:

```
postgresql://court:court@localhost:7001/courtdb
```

The tables live in the `dbo` schema, mirroring the SQL Server layout. Or open a
`psql` shell in a throwaway container with `. script/db/psql`.

## Starting from zero

To throw away every piece of local state and rebuild as if you had just
cloned:

```bash
. script/reset
```

This stops Floci, removes the containers and volumes it created (the Lambda
bundles and the database), deletes Floci's own state, and then runs the whole
`script/setup` sequence again: tool checks, Floci, bootstrap, deploy, seed.
Use it whenever you change CDK infrastructure, when something looks stuck, or
when you want a clean demo. It ends with the same two lines as step 4.

To stop the project without deleting anything:

```bash
. script/destroy
```

This stops Floci and removes its helper containers but keeps the data volumes. Stopping Docker Desktop or
Colima also works but affects every project using that engine.

If only the fixture dates have gone stale, re-seed without rebuilding:

```bash
. script/db/reset
```

The fixtures are anchored to the day they load, so a hearing seven days out
becomes six days out tomorrow and within a week nothing sits at the seven,
three and one day reminder thresholds. `. script/db/reset` reloads them and
reports what each threshold would now find:

```
hearings the reminder query returns
  seven days out    12
  three days out     3
  one day out        2
```

A zero on any line means that threshold has nothing to fire on, and the
reseed exits non-zero. It reloads every table, so anything you added by hand
is gone.

#### Seeding your own phone number

Every fixture number is in the reserved 555-01XX range, so a reminder run
against a fresh seed cannot reach a real handset. To test the whole path to
your own phone, pass it in:

```bash
. script/db/reset +14045551234
```

That rewrites the phone row behind the clean case at each lead time and
nothing else, so one person — you — has a hearing seven, three and one day
out:

```
reminder ladder now points at ***1234
  seven days out   CR-2026-000112
  three days out   CR-2026-000113
  one day out      CR-2026-000114
```

Any US format works; it is normalized to E.164 before it is written, and
rejected on the spot if it is not a valid US number. Only the last four
digits are ever printed, because the same summary goes to CloudWatch in AWS
and a number ties a person to a court case.

The number is an argument rather than a setting, the same rule
`. script/sms/verify` follows: there is no configured value that could
quietly become the destination, and the daily AWS reseed sends no number at
all. Every other fixture row keeps its unreachable 555-01XX value, so the
dirty-data scenarios still work.

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
. script/redeploy 
. script/run CourtBotMain script_helpers/events/hello-api.json
```

The response and any function error print in your terminal. The second argument is a event json file. It is
optional for Lambdas that accept an empty event:

```bash
. script/run CourtBotMessageStatus
```

`. script/redeploy` uses CDK hotswap because Floci cannot reliably apply
CloudFormation updates in place. After changing CDK infrastructure (anything
under `cdk_stack/`), use `. script/reset` instead.

To add a Lambda: add the handler under `lambda/`, register it with a unique
construct name in `cdk_stack/cdk_stack.py`, add a sample event under
`scripts/events/` if it needs one, then `. script/reset` and invoke it.
`. script/run` calls the function directly; it does not exercise SQS,
event-source mappings, retries, or a DLQ.

### Database

| Command | What it does |
|---|---|
| `. script/db/psql` | open a `psql` shell against the database |
| `. script/db/reset` | re-seed the database, re-anchoring the 7/3/1 fixture dates |
| `. script/db/reset +1...` | the same, with your own number on the case at each lead time |
| `. script/db/verify` | verify database exists and data exists with expected row counts |

The local database is Postgres standing in for the production Benchmark/Odyssey
SQL Server schema; it is not engine-compatible with SQL Server, and all SQL
against it must leave identifiers unquoted. See
[ADR 002](docs/adr/002-docker-postgres-simulates-court-case-db.md). Locally the
Lambdas are built for your machine's CPU architecture (Floci runs them
natively); in AWS they use Lambda's default x86-64.

### Sending a test text locally

Three routes, easiest first. All of them send real messages to real phones and
spend TrueDialog credit, so use a number you own. Each one texts a number you
name; to instead have your number reach the sender the way a real reminder
will — out of the court database, through the reminder query — seed it with
[`. script/db/reset +1...`](#seeding-your-own-phone-number).


#### Route 1: straight through the wrapper (no Docker, no deploy)

Confirm the credentials work. This contacts TrueDialog but sends nothing:

```bash
. script/sms/verify
```

Expect your account id, the channel, and `credentials accepted`. Then send one
text to a number you name:

```bash
. script/sms/verify +14045550142
```

It prints a TrueDialog action id. That identifies the send in the portal and
in delivery notices. `Active` means TrueDialog accepted and is dispatching; it
is not a delivery confirmation, so check the handset.

This route skips the Lambda entirely. It runs on your machine, reads `.env`
directly, and is the quickest way to tell whether a problem is your
credentials or the infrastructure.

#### Route 2: through the deployed Lambda

This exercises what actually ships: the Lambda reads its credentials from
Secrets Manager inside Floci, exactly as it will from AWS.


```bash
. script/run CourtBotMessageSender
```

`"credentials_accepted": true` means the whole chain works. Then send:


```bash
  echo '{"to": "+14045550142", "message": "Hello from GA Court Reminders"}' > /tmp/sms.json
. script/run CourtBotMessageSender /tmp/sms.json
```

After changing anything in `.env`, run `. script/reset` rather than
`. script/redeploy`. Hotswap deploys skip secret changes, so a plain deploy
leaves the old values in place and you will chase a problem that is not there.

#### Route 3: from Insomnia or curl

Import [docs/insomnia/court-reminders.json](docs/insomnia/court-reminders.json),
select the `Local (Floci)` environment. The url to use is in the output of `. script/setup`

Set that as `sender_url`, and set `test_number` to your phone. Both ship blank
so that an unconfigured request fails instead of texting someone unexpected.

Two things differ from the deployed setup, because **Floci does not provision
Lambda function URLs**. There is no local equivalent of the `SenderUrl` stack
output; what you get instead is Floci's invoke endpoint, which takes the same
`{"to", "message"}` body but needs no `x-api-key` and returns the Lambda's
whole response envelope, with the payload inside `body` as a JSON string. The
function name also changes on every `. script/reset`, so run the command
again after one.

Use only the **Sending** folder against Floci. The **Error cases** folder
describes the function URL's behaviour, which does not exist locally: the two
wrong-key requests are not refused there, they send a text.

#### When it does not work

| Symptom | Cause |
|---|---|
| `not configured: Missing TrueDialog settings` | `.env` is missing or the three values are blank |
| `503` with the same message | the deployed secret is empty; run `. script/reset` |
| `credentials_accepted: false` | TrueDialog rejects the key for that account id |
| `Not a valid US phone number` | the recipient is not ten digits with a valid area code |
| `502` with a TrueDialog status | TrueDialog refused the send; the channel or opt-in is usually why |
| Insomnia: `URL using bad/illegal format` | `sender_url` is blank; see route 3 |

A recipient who has never texted your TrueDialog number may be refused on
opt-in grounds. Texting that number from the handset once clears it.

### Text messages (TrueDialog)

Outbound SMS goes through [TrueDialog](https://api.truedialog.com/docs/). The
`lambda/truedialog/` package wraps its REST API the way `court_db` wraps the
database: handlers import only from the package root, settings come from
environment variables locally and from Secrets Manager when deployed, and the
HTTP transport is injectable so unit tests never touch the network.

```python
from truedialog import truedialog_client

result = truedialog_client().send_message("(404) 555-0142", "See you in court.")
print(result.action_id, result.status)
```

`send_message` normalizes US phone numbers to E.164, posts a push-campaign
action over the configured channel, and raises `TrueDialogApiError` (with the
HTTP status and body) when TrueDialog rejects the request. `ping()` checks
the credentials without sending anything.

The sender Lambda (`CourtBotMessageSender`) is the one Lambda outside the
database VPC, so it reaches TrueDialog and Secrets Manager over the internet
at no cost (the isolated subnets have no route out). It reads its credentials
from a Secrets Manager secret that `CourtReminderStack` creates, named by
`TRUEDIALOG_SECRET_ID` (JSON keys `api_key`, `api_secret`, `account_id`,
`channel_id`).

Developers send texts through the sender's function URL, the `SenderUrl`
stack output, or by putting a message on the outbox queue described below. The URL is public, so every request must carry the `x-api-key`
header with the value of the `SenderApiKey` secret (the `SenderApiKeySecretArn`
output; CloudFormation generates it in AWS, and on Floci it is always
`local-dev-key`). `GET` reports readiness without sending; `POST` sends one
text:

```bash
aws cloudformation describe-stacks --region us-east-2 --stack-name CourtReminderStack \
  --query "Stacks[0].Outputs" --output table
aws secretsmanager get-secret-value --region us-east-2 --secret-id <SenderApiKeySecretArn> \
  --query SecretString --output text
curl -X POST "<SenderUrl>" -H "x-api-key: <key>" -H "content-type: application/json" \
  -d '{"to": "+14045550142", "message": "Hello from GA Court Reminders"}'
```

Errors come back as JSON: 401 for a missing or wrong key, 400 for a bad
request or phone number, 502 when TrueDialog rejects the send, and 503 while
the TrueDialog secret is still empty.

[docs/insomnia/court-reminders.json](docs/insomnia/court-reminders.json) is an
[Insomnia](https://insomnia.rest/) collection covering those calls: import it,
pick an environment, and fill in `sender_url`, `api_key` and `test_number`.
All three ship blank, so a request before they are set fails rather than
texting a stranger; Insomnia cannot see `.env`. For `Dev (AWS)` those come
from the stack outputs; for `Local (Floci)` see
[Sending a test text locally](#sending-a-test-text-locally), where the URL is
different and the error cases do not apply. The dev key is a real credential,
so put it in a private environment (Insomnia leaves those out of exports)
rather than committing a filled-in copy.

#### The outbox queue

`CourtReminderStack` also creates an SQS queue, `CourtBotOutboxUrl`, wired to
the sender. A queue message body is exactly the JSON the function URL accepts,
so a reminder reaches the sender the same way by either route:

```json
{"to": "+14045550142", "message": "See you in court Thursday."}
```

Nothing produces messages yet. `CourtBotMain` will once the reminder copy has
a home; until then, put one on the queue by hand:

```bash
aws sqs send-message --region us-east-2 --queue-url <CourtBotOutboxUrl> \
  --message-body '{"to": "+14045550142", "message": "See you in court Thursday."}'
```

The sender reports failures per record, so one bad message never re-texts the
rest of its batch. A message that keeps failing moves to the dead letter
queue, `CourtBotOutboxDeadLettersUrl`, after three receives, with its payload
intact. That is the first place to look when a reminder does not arrive;
the sender's own logs deliberately carry no phone number or message text.

To exercise the queue path locally without a queue, invoke the sender with a
sample SQS event:

```bash
. script/run CourtBotMessageSender script_helpers/events/sqs-send.json
```

That file carries its own recipient, the reserved `+1 404 555 0142`, so edit
it before expecting a text. It does not consult `.env`.

Locally, put `TRUEDIALOG_API_KEY`, `TRUEDIALOG_API_SECRET`, and
`TRUEDIALOG_ACCOUNT_ID` in `.env` (see `.template.env`; `TRUEDIALOG_CHANNEL_ID`
defaults to TrueDialog's channel 22). `. script/setup` copies them into the
secret inside Floci, creates the same function URL there (its address is the
`SenderUrl` output), and the Lambda reads the secret exactly as it will in
AWS. Hotswap deploys skip secret changes, so after editing those values run
`. script/reset`. Direct invocations need no key:

```bash
. script/run CourtBotMessageSender
echo '{"to": "+14045550142", "message": "Hello from GA Court Reminders"}' > /tmp/sms.json
. script/run CourtBotMessageSender /tmp/sms.json
```

Every route takes its destination from the request, never from `.env`:
Insomnia from its own `test_number` variable, an invoke or a `curl` from the
`to` field, and `. script/sms/verify` from a phone number argument provided. The Lambda has no
configured recipient at all, which is why a message without one fails
instead of texting somebody unexpected.

Destroying `CourtReminderStack` deletes both secrets, so the TrueDialog values
must be entered again after a redeploy from scratch.

The sender is the only Lambda outside the database VPC, which is what gives it
a route to TrueDialog without paying for a NAT gateway. That is a development
compromise: production has to run every Lambda inside the VPC. See
[ADR 004](docs/adr/004-text-sender-runs-outside-the-vpc.md) for the reasoning
and what the two shapes cost.

Nothing in the test suite contacts TrueDialog. Tests must not reach an
external service or spend message credit, so the one command that can text a
real person is separate and deliberate:

```bash
. script/sms/verify
```

That checks the credentials in `.env` against the live account and sends
nothing. To send one real text, name the recipient:

```bash
. script/sms/verify +14045550142
```

The recipient is an argument rather than a setting, so no configured value
can quietly become the destination.

### Credentials and what never to commit

Four secrets exist. None of them belongs in the repository, and none is in it
today.

| Secret | Where it lives | Who creates it |
|---|---|---|
| TrueDialog API key and secret | `.env` locally, Secrets Manager when deployed | TrueDialog, in your credentials email |
| Sender API key | Secrets Manager | CloudFormation generates it; `local-dev-key` on Floci |
| Court database credentials | Secrets Manager | CloudFormation generates them |
| Your TrueDialog account id | `.env`, Secrets Manager | TrueDialog portal |

The database values in `.template.env` are the exception. `court` / `court`
are dummy credentials for the throwaway Postgres inside Floci, they are
documented deliberately, and they reach nothing real.

**Rules that matter in practice.**

`.env` is gitignored and must stay that way. Check before you commit rather
than after:

```bash
git status --short
```

If `.env` ever appears in that output, something has changed `.gitignore`.
Stop and fix that before committing.

Never paste a key into a pull request, an issue, a Slack message, or a
screenshot. If you need to show that something is set, show its length or its
last four characters.

The Insomnia collection ships with `api_key` blank on purpose. Insomnia
excludes **private** environments from exports, so put a real key in a private
environment. A filled-in collection exported normally carries the key in
plain text.

Never paste a credential into a command you will run, because your shell keeps
history. `. script/sms/verify` reads `.env` rather than taking the key as an
argument for exactly this reason.

Deployed secrets are readable by anyone with AWS access to the account, which
is the intended design: the Lambda reads them at runtime. Read one back with
the CLI when you need it, rather than storing a second copy anywhere.

**If a credential does leak.** Rotate it first, then clean up. For TrueDialog
that means asking them to reissue the key and secret, and updating `.env` and
the deployed secret. Deleting the commit is not enough: anything pushed to
GitHub should be assumed to have been seen, and rewriting published history
does not recall it.

To check that nothing sensitive is about to be committed, search your staged
changes for the values you know are secret:

```bash
git diff --cached | grep -i -E "api[_-]?key|secret|password|token"
```

That catches the obvious cases. It is a habit, not a guarantee.

### Checks

```bash
. script/test      # unit tests, plus integration tests when the stack is up
. script/lint          # ruff check
. script/format       # ruff format
```

## AWS deployment

Merges to `main` deploy through the repository's GitHub Actions pipeline.
Manual deployment needs the AWS CLI and configured credentials. Do not set
`AWS_ENDPOINT_URL` when targeting real AWS.

The same two stacks deploy: `CourtDatabaseStack` becomes RDS SQL Server
Express (instance `courtbot-dev`) in an isolated-subnet VPC with generated
credentials in Secrets Manager, and `CourtReminderStack` places the Lambdas
in that VPC, except the text sender, which runs outside it behind a public
function URL (see [Text messages](#text-messages-truedialog)). The instance
is not reachable from outside the VPC.

Add project dependencies with `uv add <dependency>`

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
fixture dates without changing the scripts, run `. script/db/reset` locally, or in
AWS deploy with a new `reseed` value:

```bash
uv run cdk deploy CourtReminderStack -c reseed=$(date +%s)
```

The stack output `CourtDatabaseSeedHearings` reports the seven-day
reminder-query row count right after seeding, which should be 12.

### The dev database re-seeds itself daily

Deploying is not frequent enough to keep date-relative fixtures useful, so the
`CourtDatabaseDailyReseed` EventBridge rule invokes `CourtBotDatabaseLoader`
every day at 07:00 UTC, before the daily reminder run reads the database. It
sends the same empty event `. script/db/reset` sends, and the CloudWatch log
for that run prints the row counts and how many hearings sit at each of the
seven, three and one day thresholds.

This reloads every table, so **anything entered in the AWS dev database by
hand is gone the next morning**. The schedule exists only in AWS mode; on
Floci a person runs `. script/db/reset`. Nothing in this stack is safe to
point at a database anyone depends on.
