# ADR-001: Use uv for dependency management

## Status

Accepted

## Context

The project originally used pip and venv for dependency management. When consolidating the choose-your-own-adventure demo and the Twilio hello world into a single structured repo, we needed reproducible builds, faster installs, and a single tool for creating virtual environments, installing packages, and locking dependencies — something more hardened and future-proof as the project matures.

## Decision

We will use [uv](https://docs.astral.sh/uv/) as our Python package and project manager. Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. A `requirements.txt` is exported for Azure Functions deployment via `make requirements`.

## Consequences

- **Easier:** Onboarding is a single `uv sync` command. Lock file guarantees reproducible installs across machines and CI.
- **Harder:** All contributors must install uv. Teams familiar only with pip/venv need to learn uv commands (`uv add`, `uv sync`, `uv run`).
  - Note, we have provided instructions for installation in the README, and most development tasks are standardized within the Makefile, so developers won't need to do too much specifically with `uv`
