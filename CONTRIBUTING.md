# Contributing

Thanks for your interest in the GA Court Reminders project!

## Branch Naming

We generally do development tied to GitHub issues.  Do development on a branch with name tied to the issue: use the pattern `issue-XX-short-description`, e.g. `issue-18-repo-structure-update`

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
uv add <package>
```

`requirements.txt` is generated automatically during CI deployment — no need to commit it.

## Adding a New Scenario

> This section will be fleshed out after issue #11 is completed.

Place new scenario modules under `src/court_reminder/scenarios/`.
