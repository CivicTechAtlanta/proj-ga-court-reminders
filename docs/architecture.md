# Architecture

High-level architecture for the GA Court Reminders system.

> See the [FigJam board](https://www.figma.com/board/Iy3apztPLkVpphvhcbO9q3/2025.11-Georgia-Court-reminders?node-id=109-594&t=9oD6U3qNmy7vGaTx-1) for the visual diagram

## Overview

The system finds court hearings due for a reminder and sends the defendant an
SMS. It runs as AWS Lambda functions defined in CDK, reads hearings from a
court case database, and sends text messages through
[TrueDialog](https://api.truedialog.com/docs/).

Everything also runs on a developer machine against [Floci](https://floci.io),
an AWS emulator, with Postgres standing in for the production SQL Server. The
same CDK code deploys to both.

## Components

- **CourtBotMain** -- queries the court database for hearings due a reminder.
- **CourtBotMessageSender** -- sends one text through TrueDialog. Reached by a
  queue message, an HTTPS request to its function URL, or a direct
  invocation; all three carry the same `{"to", "message"}` JSON.
- **CourtBotMessageResponse** -- will handle replies from recipients, including
  opt-outs. Still a stub.
- **CourtBotMessageStatus** -- will handle delivery notices. Still a stub.
- **CourtBotDatabaseLoader** -- loads schema and fixtures during a deploy, as a
  CloudFormation custom resource.
- **Court case database** -- RDS, holding the Odyssey-shaped hearing tables.
  SQL Server Express in AWS, Postgres under Floci.
- **Outbox queue** -- SQS, feeding the sender, with a dead letter queue for
  messages that keep failing. Nothing produces messages yet.
- **Sent reminders table** -- DynamoDB, recording which reminders already went
  out so a queue retry cannot text somebody twice.
- **Secrets Manager** -- the database credentials, the TrueDialog API key and
  secret, and the key guarding the sender's public URL.

## Networking

Every Lambda except the sender runs in an isolated-subnet VPC beside the
database, with no route to the internet. The sender runs outside it, because
it has to reach TrueDialog and a NAT gateway would cost more than the rest of
the development environment. Production must put it inside the VPC; see
[ADR 004](adr/004-text-sender-runs-outside-the-vpc.md) for the reasoning and
what each shape costs.

## Not yet decided

- What produces outbox messages, and where the reminder copy lives.
- The conversation flow for replies, and how opt-outs are tracked.
