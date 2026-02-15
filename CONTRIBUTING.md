# Contributing

Thanks for your interest in the GA Court Reminders project!

## Branch Naming

Use the pattern `issue-XX-short-description`, e.g. `issue-18-repo-structure-update`.

## Pull Requests

- PRs require at least 1 review before merging
- Use **squash merge** to main

## Local Development Setup

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. From the repo root:
   ```bash
   make setup
   ```
3. Start the Azure Function locally:
   ```bash
   make run
   ```

## Running Tests

```bash
make test
```

## Linting

```bash
make lint
```

## Adding a Dependency

```bash
cd choose-your-own-adventure-demo
uv add <package>
make requirements   # regenerate requirements.txt for Azure deployment
```

## Adding a New Scenario

> This section will be fleshed out after issue #11 is completed.

Place new scenario modules under `choose-your-own-adventure-demo/src/court_reminder/scenarios/`.
