# ADR-005: Scripts to Rule Them All 

## Status
Accepted

## Context
We have been abusing make. We've been using it as a jerry-rigged `npm run`. `make` is meant to *make* things.

## Decision

Build out a set of scripts to execute common developer tasks, such as setting up the project, testing, or tearing things down. To read more about the pattern, please see: https://github.com/github/scripts-to-rule-them-all.

## Consequences

We no longer have an ever expanding makefile. Instead, our scripting needs are organized under `script/`. This pattern is pretty extensible. New scripts can be created as needed. Domain specific scripts should live under the folder named for that domain (see `db` or `sms`).
