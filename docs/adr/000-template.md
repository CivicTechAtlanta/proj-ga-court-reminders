# ADR-NNN: Title

## Status

Proposed | Accepted | Deprecated | Superseded by [ADR-NNN](NNN-title.md)

## Context

What is the issue that we're seeing that is motivating this decision or change?

## Decision

What is the change that we're proposing and/or doing?

## Consequences

What becomes easier or more difficult to do because of this change?

---

# Example: ADR-001: Use uv for dependency management

## Status

Accepted

## Context

The project originally used pip and venv for dependency management. As the team grew, we needed reproducible builds, faster installs, and a single tool for creating virtual environments, installing packages, and locking dependencies.

## Decision

We will use [uv](https://docs.astral.sh/uv/) as our Python package and project manager. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. A `requirements.txt` is exported for Azure Functions deployment via `make requirements`.

## Consequences

- **Easier:** Onboarding is a single `uv sync` command. Lock file guarantees reproducible installs across machines and CI
- **Harder:** All contributors must install uv. Teams familiar only with pip/venv need to learn uv commands (`uv add`, `uv sync`, `uv run`)
