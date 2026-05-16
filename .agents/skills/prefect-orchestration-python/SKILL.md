---
name: prefect-orchestration-python
version: 1
description: Skill for designing and operating data ingestion workflows in Python using Prefect OSS 3.x, with well-modelled flows, scheduling, retries, and observability, focused on a single-VM MVP.
---

# Skill: prefect-orchestration-python

## Purpose

This skill guides Copilot when designing, reviewing, or generating code related to data workflow orchestration in Python using Prefect OSS (v3.x), specifically in the context of an MVP deployed on a single machine (e.g. Oracle ARM VM) with Docker Compose.

## When to Use This Skill

Activate when the task involves:

- Defining or modifying Prefect `flows` and `tasks`.
- Designing `deployments`, queues, agents, and schedules (cron or interval-based).
- Adding `retries`, `timeouts`, concurrency limits, and state handling.
- Integrating Prefect with an ingestion pipeline (e.g. `run_all_sources`, `run_source`).
- Deciding between Prefect vs. system `cron`, or discussing orchestration trade-offs.

## Default Decisions

- Version: Prefect OSS 3.x; do not use Prefect Cloud unless explicitly requested.
- Deployment: `prefect server` + `prefect agent` in Docker Compose, pointing to the same VM.
- Language: Python 3.12+, strict typing.
- Complexity limit: avoid giant DAGs; prefer small, composable flows.

## Flow Design Guidelines

- Each `flow` must:
  - Have a clear, bounded purpose.
  - Be as pure as possible: separate IO and side effects from business logic.
  - Accept serialisable parameters (Pydantic/JSON-like) and avoid heavy objects.

- Recommended pattern for multi-source ingestion:
  - `flow run_all_sources()`
    - Fetches the list of active sources from the application/domain layer.
    - Launches subflows/tasks `run_source(source_id)` with a concurrency limit.
  - `flow run_source(source_id)`
    - Orchestrates connector execution, `RawDocument` persistence, and event extraction.
  - `flow test_source(source_id)`
    - Runs a limited ingestion and returns a health summary.

- Use pure tasks for small units (fetch, parse, persist, notify) and flows for orchestration.

## Scheduling

- Prefer the Prefect scheduler over system `cron`.
- Default rules:
  - `run_all_sources`: at least once per day (e.g. `0 12 * * *`).
  - Critical or highly dynamic sources: additional deployments with higher frequency.
- Schedules must be version-controlled as code (infra-as-code) and must not depend on manual configuration.

## Retries, Timeouts, and Limits

- Always set:
  - Reasonable `retries` and `retry_delay` for network tasks.
  - `timeout` for tasks involving scraping, headless browsers, or external API calls.
- Use concurrency limits per source type or domain (e.g. do not launch 50 scrapers of the same site simultaneously).

## Observability

- Leverage Prefect to:
  - Record the state of each `flow` and `task`.
  - Query failed/`late` runs and restarts.
  - Add structured logs (`source_id`, `ingestion_run_id`, etc.) from tasks.

## Integration with DDD/Hexagonal Architecture

- Prefect must live in the infrastructure / orchestration layer.
- `flows` must orchestrate application-layer use cases; they must not contain domain logic.
- Business logic (validation, deduplication, etc.) is modelled in domain services, called from tasks.

## Code Generation Rules

When the user asks for Prefect-related code:

1. First propose the flow/task structure and how it fits the use cases.
2. Generate code with type annotations, clearly separating domain, application, and infrastructure.
3. Show `Deployment` and `Schedule` examples when relevant.
4. Include logging, retry, and concurrency recommendations.

## What to Avoid

- Modelling everything as a single giant DAG that is hard to maintain.
- Mixing complex domain logic inside Prefect tasks.
- Relying exclusively on `cron` without leveraging Prefect's UI and state tracking.
- Introducing Prefect Cloud or paid features without an explicit request.

## Recommended Tooling

- Manage flow dependencies and runtime environments with **uv** (pyproject.toml + uv.lock).
- Run type checks on Prefect-related code using **ty**.
- Apply **Ruff** as the linter/formatter for all flow and task code.
- Centralise dev commands with **mise** (e.g. `mise run flows:test`, `mise run flows:lint`, `mise run flows:typecheck`).
