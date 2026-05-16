---
name: ingesta-eventos-madrid
version: 1
description: Skill for designing, implementing, and evolving a cultural event ingestion system for Madrid using Python 3.12+, DDD + Hexagonal architecture, PostgreSQL, Prefect, qcrawl, and justhtml — prioritising a stable MVP with connectors, normalisation, scheduling, and observability.
---

# Skill: ingesta-eventos-madrid

## Purpose

This skill guides Copilot when working on the hazlo MVP: a cultural event ingestion system for Madrid.

Priorities:

- Source modelling (`Source` entity).
- Ingestion connectors for websites, XML/RSS feeds, and email newsletters.
- Event normalisation to a canonical model.
- Ingestion scheduling and observability.
- Operation without complex UI; preference for CLI, jobs, and a minimal API.

## When to Use This Skill

Activate when the task is related to any of these areas:

- Designing ingestion architecture.
- Creating or modifying connectors for heterogeneous sources.
- Defining database schemas for sources, runs, and extracted events.
- Implementing scheduling with Prefect.
- Designing validation, data quality, and connector health checks.
- Generating Python backend or scraping job code.
- Producing technical documentation for the ingestion pipeline.

## Default Technical Decisions

### Preferred Stack

- Language: Python 3.12+
- Architecture: DDD + Hexagonal (Domain, Application, Infrastructure)
- Backend/API: FastAPI only when a minimal API needs to be exposed
- Validation/configuration: Pydantic v2
- Persistence: SQLAlchemy 2.0 async
- Database: PostgreSQL with JSONB; PostGIS optional later
- Crawling: qcrawl
- HTML parsing: justhtml
- Scheduling/orchestration: Prefect OSS 3.x
- Testing: pytest, Factory Boy, Testcontainers
- MVP deployment infra: Docker Compose on an Oracle ARM Always Free VM
- No Kubernetes in this phase unless explicitly requested

### Design Principles

- Prefer composition over inheritance.
- Separate scraping/parsing from domain and use cases.
- Use ports and adapters to decouple connectors and persistence.
- Design for multiple source types from day one.
- Do not mix extraction logic with business decisions.
- All code with strict type hints, compatible with ty strict mode.

## Minimum Conceptual Model

### Core Entities

- `Source` — represents a configurable, activatable/deactivatable source.
- `IngestionRun` — represents a single ingestion execution for a source.
- `RawDocument` — raw content retrieved (HTML, XML, email, JSON, text).
- `ExtractedEvent` / `EventDraft` — normalised/intermediate event representation.

### Required Capabilities

Every proposal or implementation must account for:

- Activating/deactivating sources.
- Configuring each source (url, type, frequency, parsing parameters, credentials if applicable).
- Running connector tests with a short result summary.
- Recording per-run metrics.
- Maintaining a health status per source: `OK`, `DEGRADED`, `FAILING`.
- Tagging data quality: `GOOD`, `SUSPECT`, `INVALID`.
- Preserving raw documents to allow reprocessing later.

## Recommended Patterns

### Architecture

Always use this layering:

```
domain/
    entities, value objects, business rules

application/
    use cases, ports, orchestration

infrastructure/
    connectors, repositories, DB adapters, Prefect, qcrawl, justhtml
```

### Connector Pattern

Use a connector registry keyed by `connector_type` with an interface like:

```python
fetch_raw_documents(source: Source) -> list[RawDocumentDTO]
test_connection(source: Source) -> ConnectorHealth
```

Supported types:

- `WEB_STATIC`
- `WEB_DYNAMIC`
- `RSS`
- `XML_FEED`
- `EMAIL_NEWSLETTER`

## Scheduling

### Default Rule

- Schedule `run_all_sources()` at least once per day.
- Default time: 12:00.
- Allow each source to have its own frequency.

### Recommendation

- Prefer Prefect over system cron.
- Use retries, timeouts, concurrency limits, and observability from day one.

## Quality and Observability

Whenever an ingestion task is designed or implemented, include:

- Structured logging per `source_id` and `ingestion_run_id`.
- Minimum metrics: documents retrieved, events extracted, valid events, errors, duration.
- Strategy for silent degradation: detect when a source keeps responding but stops producing events.

## Code Generation Rules

When the user asks for code:

1. Start with tests or with the testing strategy.
2. Generate modern, async Python where it makes sense.
3. Use explicit names and avoid obvious comments.
4. Avoid complex JS frameworks unless strictly necessary.
5. Do not design complex UI in this phase.
6. Do not write to remote repos or execute destructive actions.

## What Copilot Should Do Automatically

When detecting tasks in this skill's domain, Copilot should tend to:

- Propose simple, robust solutions for the MVP.
- Avoid over-engineering.
- Choose Docker Compose over Kubernetes.
- Choose PostgreSQL over unnecessary polyglot stacks.
- Choose a minimal API/CLI over a UI.
- Always preserve the ability to grow without rewriting the domain.

## What to Avoid

- Kubernetes for this MVP without clear justification.
- Premature microservices.
- Mixing scraping, parsing, validation, and persistence in monolithic scripts.
- Designing a mobile app or complex frontend before stabilising ingestion.
- Assuming all sources will have stable HTML.

## Companion Skills

This skill works together with:

- `scraping-qcrawl-justhtml` — for connector and parsing implementation details.
- `prefect-orchestration-python` — for flow design, scheduling, and observability.

## Recommended Tooling

- Project and dependency manager: **uv** (pyproject.toml + uv.lock, environments managed by uv).
- Primary type checker: **ty** (`ty check`) for fast, strict type checking.
- Linter/formatter: **Ruff** as a single tool for linting and formatting (replaces Flake8/Black/isort).
- Environment and task manager: **mise**, using `.mise.toml` to pin tool versions (python, uv, ty, ruff, docker, etc.) and define standard tasks (`mise run lint`, `mise run typecheck`, `mise run test`, `mise run ingest`, etc.).

All instructions and command examples must assume this toolchain (uv + ty + Ruff + mise) unless the user states otherwise.
