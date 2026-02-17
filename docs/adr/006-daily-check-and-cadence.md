# ADR-006: Daily case check, reminder dispatch, and cadence configuration

## Status

Proposed

## Context

The court reminder system has two distinct outbound workloads that run on a schedule rather than in response to inbound messages:

1. **Daily case check** - evaluates the state of every active case once per run and dispatches messages as appropriate (reminders, missed date notices, rescheduled notices)
2. **Reminder dispatch** - sends reminders at configured thresholds before a court date based on a configurable cadence

Both workloads run as Azure Functions timer triggers (per [ADR-005](005-compute-and-inbound-handling.md)). This ADR documents the logic for the daily case check, the cadence configuration model, and how the two workloads relate.

### Daily case check logic

For each case in the active queue, the following checks run in order on each invocation. The loop exits (skips to the next case) as soon as a condition is met.

```
for each active case:
    if court date was missed:
        if within grace period (30 days, per Georgia law):
            if rescheduled:
                send "rescheduled" message
                resume cadence for new court date - only thresholds still in the future
            else:
                check cadence thresholds for new date (if set)
        else:
            send "missed court date / warrant" message
            remove case from queue  [terminal]
        exit loop for this case

    if case is paid:
        remove case from queue  [terminal]
        exit loop for this case

    if it is a reminder threshold unit before court date:
        send "{n} units before court date" message
        exit loop for this case
```

**Rescheduled cadence behavior** - when a court date is rescheduled, reminders do not restart from the full threshold set. Only thresholds that still fall in the future relative to the new court date are sent. For example, if the new date is 4 units away, only the 3-unit and 1-unit reminders will fire - the 7-unit reminder is skipped since that window has already passed.

**Terminal states** - cases are permanently removed from the queue when:
- Case is paid
- Grace period expires without rescheduling (warrant state)

All other exits are non-terminal - the case remains in the queue and will be re-evaluated on the next run.

**Grace period** - fixed at 30 days, per Georgia law. This is not a configurable parameter.

### Cadence configuration

The reminder thresholds (e.g. 7/3/1) and the unit of time are both configurable via a checked-in config file. This allows the same codebase to run in production (days) and demo (minutes or seconds) without code changes.

**Config file approach** is the right home for these parameters because:
- Version-controlled alongside the code - changes are reviewed in PRs
- Consistent with the flow YAML approach established in [ADR-003](003-message-flow-definition-format.md)
- Environment-specific overrides can be applied via `local.settings.json` for local development without modifying the checked-in config

### Options considered for cadence config location

| Option | Pros | Cons |
| --- | --- | --- |
| **Config file in Git** | Version-controlled; PR-reviewable; consistent with flow YAML approach; easy to diff across environments | Requires a deploy to change; not suitable for runtime tuning |
| **Environment variables only** | Easy to change per environment without a deploy; standard Azure Functions pattern | Not version-controlled; harder to review and audit; easy to lose track of values across environments |
| **Azure App Configuration** | Centralized; supports feature flags and dynamic refresh | Another Azure service to provision and manage; overkill for a small fixed parameter set |
| **Hardcoded constants** | Simplest; no config infrastructure needed | Can't vary between prod and demo without code changes; defeats the purpose of configurable cadence |

## Decision

**Daily case check:** Azure Functions timer trigger running once per cadence unit (e.g. once daily in production, once per minute in demo). The check loop evaluates all active cases on each run using the logic above.

**Cadence configuration:** Config file checked into Git (`config/settings.yml`), with the following parameters:

```yaml
reminder_cadence:
  thresholds: [7, 3, 1]    # how many units before court date to send reminders
  unit: days               # days | minutes | seconds
  grace_period_days: 30    # fixed per Georgia law - do not change
```

The timer trigger cron expression is derived from the `unit` parameter at deploy time:
- `unit: days` - timer runs once daily (e.g. `0 0 8 * * *` for 8am)
- `unit: minutes` - timer runs once per minute (`0 * * * * *`)
- `unit: seconds` - timer runs once per second (`* * * * * *`)

Environment-specific overrides (e.g. for local development) can be set in `local.settings.json` and are not checked into Git.

## Consequences

**Easier:**
- Switching between production and demo timing requires only a config change and redeploy - no code changes.
- The grace period value is documented and traceable to Georgia law. Any future change to the legal requirement has a clear place to land.
- Terminal state logic (paid, warrant) is explicit in the check loop - cases are removed cleanly and don't accumulate in Table Storage indefinitely.
- Adding a new reminder threshold (e.g. a 14-day reminder) requires a one-line config change.
- Rescheduled cadence behavior is deterministic - thresholds are evaluated against the new court date at runtime using `last_reminder_sent` from the CaseQueue table to determine which reminders still need to fire.

**Harder:**
- The timer trigger cron expression must be kept in sync with the `unit` config parameter. If these drift (e.g. unit says `days` but cron fires every minute) the system will send duplicate messages. This should be validated at startup.
- The demo's compressed time means the system can exhaust a full scenario in minutes - the Function App must handle rapid sequential timer invocations cleanly without state collisions in Table Storage (per [ADR-002](002-conversation-state-storage.md)).
- Case state in Table Storage must store both the original and rescheduled court dates to support the grace period check and the partial cadence resume logic (see ADR-002 for updated schema).

**Relationship to other ADRs:**
- Timer trigger Functions share the same Function App as the inbound message HTTP trigger per [ADR-005](005-compute-and-inbound-handling.md).
- Case state (current queue status, court dates, grace period tracking) is persisted in Table Storage per [ADR-002](002-conversation-state-storage.md).
- The `config/settings.yml` file follows the same version-control-as-source-of-truth principle as the flow YAML files per [ADR-003](003-message-flow-definition-format.md).
- Demo scenario data (mock court dates used to exercise this logic) is defined per [ADR-004](004-demo-scenario-data-and-selection.md).
