# GitHub Copilot Instructions — hazlo

This file contains workspace-level instructions for GitHub Copilot.
Apply these to all code generation, review, and assistance tasks in this repository.

> **Full documentation**: [docs/](../docs/) — especially [docs/ai-context.md](../docs/ai-context.md)
> for a dense AI-oriented knowledge base.

---

## Project Overview

**hazlo** is a source-available cultural event agenda for modern cities.
Core capabilities: multi-source ingestion, event normalisation, human-in-the-loop review,
and a minimal administration panel for managing sources.

This is a single-VM MVP. Do not introduce distributed systems complexity unless explicitly requested.

---

## Architecture

Always follow **DDD + Clean Architecture** with three layers:

```
domain/          ← entities, value objects, business rules — no framework dependencies
application/     ← use cases, ports, orchestration
infrastructure/  ← repositories, DB adapters, HTTP API, connectors, Prefect, qcrawl
```

- Prefer composition over inheritance.
- Use ports and adapters to decouple connectors and persistence.
- Prefect flows live in `infrastructure/`; they orchestrate application use cases — never domain logic.

### HTMX + SSR UI Architecture (MANDATORY)

Always preserve the server-rendered shell and apply HTMX as progressive enhancement:

- Hard refresh must render full page shell via Jinja `base.html`.
- Internal admin navigation must swap only `#main-content` (do not replace whole `<body>`).
- Keep nav/header persistent across section changes.
- Use canonical trailing-slash admin list routes to avoid redirect hops.
- Prefer explicit HTMX attributes (`hx-get`, `hx-target`, `hx-swap`, `hx-push-url`) on navigation links when inherited boost behavior is fragile.
- For full-page templates, use `{% extends base %}` and select base template via request type (`HX-Request` vs normal request).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| API | FastAPI (latest stable) |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.x async |
| Database | PostgreSQL with JSONB |
| Crawling | qcrawl |
| HTML parsing | justhtml |
| Orchestration | Prefect OSS 3.x |
| Frontend | HTMX + Jinja2 + Tailwind CSS |
| Testing | pytest + Factory Boy + Testcontainers |
| Infra | Docker Compose on Oracle ARM VM |

---

## Tooling

| Tool | Role |
|---|---|
| **uv** | Package manager, virtual environments, lockfile (`pyproject.toml` + `uv.lock`) |
| **mise** | Tool version manager + task runner (`.mise.toml`) |
| **ty** | Static type checker (strict mode) |
| **Ruff** | Linter and formatter (replaces Flake8 + Black + isort) |

Standard tasks (defined in `.mise.toml`):

```bash
mise run dev        # start app in dev mode
mise run test       # run test suite
mise run typecheck  # ty check src
mise run lint       # ruff check src
mise run fmt        # ruff format src
```

---

## Python Code Conventions

Follow modern Python 3.13 patterns at all times:

- Always add `from __future__ import annotations` at the top of every module.
- Use `X | None` instead of `Optional[X]`.
- Use `list[X]`, `dict[K, V]` instead of `List[X]`, `Dict[K, V]`.
- Use `TYPE_CHECKING` blocks for type-only imports (`Sequence`, `Protocol`, `Callable`, etc.).
- Use `match/case` for multi-branch logic instead of long `if/elif` chains.
- Use `@dataclass(frozen=True, slots=True)` for immutable boundary models.
- Never add `# noqa` hacks — fix the issue properly.
- Fix circular imports with `TYPE_CHECKING`, not by relaxing boundaries.

---

## Domain Model (Key Entities)

- `Source` — a configurable, activatable/deactivatable ingestion source.
- `IngestionRun` — a single execution of ingestion for one source.
- `RawDocument` — raw content retrieved (HTML, XML, email, JSON).
- `EventDraft` — normalised intermediate event representation pending review.
- `Event` — reviewed and published event.

Data quality labels: `GOOD`, `SUSPECT`, `INVALID`.
Source health states: `OK`, `DEGRADED`, `FAILING`.

---

## Ingestion Connector Pattern

Every connector must implement:

```python
fetch_raw_documents(source: Source) -> list[RawDocumentDTO]
test_connection(source: Source) -> ConnectorHealth
```

Source types: `WEB_STATIC`, `WEB_DYNAMIC`, `RSS`, `XML_FEED`, `EMAIL_NEWSLETTER`.

Split connectors into three functions:
- `fetch` — download raw content
- `parse` — extract structured DTOs from raw content
- `map_to_domain` — project DTOs to domain entities

---

## Scheduling Defaults

- Schedule `run_all_sources()` at least once per day at 12:00 (`0 12 * * *`).
- Prefer Prefect scheduler over system cron.
- All schedules must be version-controlled as code.

---

## Testing

- Write tests before or alongside implementation.
- Domain tests must not depend on infrastructure (no DB, no HTTP).
- Use Testcontainers for integration tests that need PostgreSQL.
- Remove unused fixtures and parameters to avoid Pylance warnings.
- Prefix unused-but-required parameters with `_`.

---

## What to Avoid

- Kubernetes for this MVP without explicit justification.
- Premature microservices.
- Mixing scraping, parsing, validation, and persistence in a single script.
- Complex frontend before ingestion is stable.
- `Optional[X]` — use `X | None`.
- Runtime imports of typing generics — use `TYPE_CHECKING`.

---

## Available Skills

The following workspace skills are available in `.agents/skills/`:

| Skill | Path | When to Use |
|---|---|---|
| `ingesta-eventos-madrid` | `.agents/skills/ingesta-eventos-madrid/SKILL.md` | Overall project domain, architecture decisions, MVP scope |
| `scraping-qcrawl-justhtml` | `.agents/skills/scraping-qcrawl-justhtml/SKILL.md` | Connector implementation, HTML/XML parsing |
| `prefect-orchestration-python` | `.agents/skills/prefect-orchestration-python/SKILL.md` | Flow design, scheduling, retries, observability |

---

## Versioning

- **Timestamp format**: `YYYYMMDDHHMM` — no semver (`v1.2.3`).
- **Dev**: `__version__ = "0.0.0"` in `hazlo/__init__.py`. Don't modify during development.
- **Release**: automatic on merge to `main`. CI bumps, commits, tags, and creates GitHub Release.
- **Branching**: `dev` for daily work, `main` for releases. All PRs target `dev`.
- **Check**: `mise run version`.

## License

hazlo is source-available software licensed under the **Hazlo Source-Available Ethical License 1.0 (HSEL-1.0)**.
It is not open source in the OSI sense. See `LICENSE` and `ETHICAL-USE.md` for details.

---

## Documentation (MANDATORY)

Documentation is not optional. This is an open-source project — docs are the first impression.

**Rule: every code change that affects behavior MUST update documentation.**

Before finishing any task, verify:

| If you changed... | Update this file |
|---|---|
| Entities, routes, conventions, tooling, architecture | `docs/ai-context.md` |
| Setup steps, tech stack, features visible to new users | `README.md` |
| Added, changed, or removed a feature | `CHANGELOG.md` |
| Dev workflow, conventions, versioning rules | `CONTRIBUTING.md` |

When in doubt, update. Stale docs are worse than no docs.
