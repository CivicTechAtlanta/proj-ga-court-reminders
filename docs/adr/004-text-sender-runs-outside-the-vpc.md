# ADR-004: The text sender runs outside the VPC in development

<!-- 003 is held by the public-dev-database-and-HTTP-API decision, which is
     parked uncommitted on the local branch wip/public-dev-database-http-api
     rather than in this tree. -->

## Status

Accepted (2026-09-11)

## Context

`CourtBotMessageSender` calls TrueDialog at `api.truedialog.com` to send a
text. The other Lambdas only talk to the court database and to AWS services.

`CourtDatabaseStack` puts everything in isolated subnets with no NAT gateways,
so nothing in the VPC has a route to the internet. A Lambda attached to that
VPC therefore cannot reach TrueDialog. This holds even if the subnets are made
public: Lambda network interfaces never receive public addresses, so a public
subnet alone buys no egress. TrueDialog is not an AWS service, so an interface
endpoint cannot substitute either. The only ways out are a NAT gateway, a
self-managed NAT instance, or leaving the function outside the VPC.

This is a shared development environment for a volunteer team, sized for the
lowest tier of every service. The production system is different: it will
carry real defendant names, case numbers, and phone numbers, so it has to sit
inside a VPC.

The sender needs nothing from the database. It receives a rendered message and
a phone number, either on the outbox queue or over its function URL.

## Decision

**In development the sender runs outside the VPC.** It is the only Lambda
without a `VpcConfig`, and so the only one with internet access. The other
four keep their place in the isolated subnets alongside the database. The
sender reads its two secrets over the public AWS endpoints rather than through
the VPC's Secrets Manager endpoint.

**In production every Lambda belongs in the VPC**, with the sender's egress
provided by a NAT gateway. The data is the reason, not the cost. Nothing in
the application code changes: the sender takes its placement from
`_database_placement()` like the others, so this is a one-line reversal in
`cdk_stack.py` plus a NAT gateway in `CourtDatabaseStack`.

## Costs

Monthly, US East (Ohio), 730 hours, from the AWS Price List API on 2026-09-11.
Lambda, SQS, CloudWatch Logs, and the function URL fall inside permanent free
tiers at this volume and are omitted.

| | Sender outside (today) | Uniform VPC with NAT |
|---|---|---|
| As the stack is coded now | 50.22 | 83.07 |
| At the lowest tier of every service | 26.86 | 59.71 |
| Lowest tier, Secrets Manager endpoint dropped | n/a | 52.41 |

Moving the sender in costs **32.85/month** for the NAT gateway, plus 0.045 per
GB processed. That single line item exceeds the database instance.

Some of it comes back. Once a NAT gateway exists, the Lambdas can reach
Secrets Manager over the internet, so the interface endpoint and its 7.30 per
AZ become optional, and the true increase is about 25.55. Production would
want a NAT gateway per availability zone for failover, which doubles the
gateway line to 65.70.

The stack is not at the lowest tier today: the database is a `db.t3.small`
where SQL Server Express supports `db.t3.micro`, and the Secrets Manager
endpoint spans both subnets where one would do. Those two together are the
23.36 gap between the rows above.

## Consequences

- **Easier:** the sender reaches TrueDialog at no cost, and developers reach
  the sender at no cost through a function URL. The development environment
  stays near the price of the database alone.
- **Harder:** the Lambdas are not uniform, which is a surprise worth the
  comment that sits above the sender in `cdk_stack.py`. The sender has no
  database access, so giving it a database-backed job later means either
  moving it in, and paying for egress, or splitting the work.
- **Security:** the sender's traffic to TrueDialog and to Secrets Manager
  leaves over the public internet rather than staying inside the VPC. Both are
  TLS, and the payload is a phone number and a reminder, but it is a wider
  exposure than the rest of the system accepts. This is the specific thing
  that must change before real case data flows.
- Inbound access is unaffected by any of this. A function URL does not
  traverse the VPC, so moving the sender in would not restrict who can call
  it; the `x-api-key` check is what does that, and it stays either way.
