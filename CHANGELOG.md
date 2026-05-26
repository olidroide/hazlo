# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **Versioning**: This project uses **timestamp-based versioning** (`YYYYMMDDHHMM`), NOT Semantic Versioning.
> Dev version is `0.0.0`. Releases use `mise run release`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## [Unreleased]

### Fixed

- **Repository upsert bug**: `EventRepository.save()` and `SourceRepository.save()` used `session.add()` which fails on duplicate entities. Changed to `session.merge()` for upsert behavior.
- **LLM provider save**: `LLMProviderRepository.save()` used `session.add()`. Changed to `session.merge()` to allow provider updates.
- **Prefect deployment entrypoints**: `from_source().deploy()` corrupted module-path entrypoints to file paths. Fixed by using `client.create_deployment()` directly with explicit `entrypoint` parameter.
- **Docker DATABASE_URL**: `${DATABASE_URL:-...}` picked up host `.env` value. Changed to use shared `POSTGRES_*` variables for Docker-internal connections.
- **Docker build**: hatchling requires `README.md` in build context. Added `!README.md` to `.dockerignore`.

### Added

- **TDD enforcement**: Pre-commit hook (`.githooks/pre-commit`) blocks commits with `hazlo/` changes but no `tests/` changes. Emergency bypass: `git commit --no-verify`.
- **Testcontainers integration tests**: Added tests for `EventRepository.save()` merge behavior to catch upsert bugs.
- **Troubleshooting guide**: Added common issues section to README (Docker build, Prefect flows, database connections, LLM performance).

### Changed

- **Documentation**: Added "Lessons Learned" section to `.agents/AGENTS.md` covering repository patterns, testing strategy, Prefect entrypoint bugs, and performance notes.

## [202505191200] - 2025-05-19

### Added

- Core domain model: `Event`, `Source`, `Review` entities with value objects
  (`Location`, `Price`, `TicketInfo`)
- Event status state machine: `pending` → `approved` → `rejected` → `published`
- Source administration panel (list, create, detail, toggle, on-demand extraction)
- Event review flow (list by status, approve/reject/edit, audit trail)
- Human-in-the-loop review with HTMX partial updates
- Multi-source ingestion via adapter pattern (`BaseSourceAdapter`)
- Prefect-scheduled flows (`ingest-all-sources` every 30 min, `ingest-single-source`)
- SQLAlchemy 2.x async repositories for events, sources, and reviews
- FastAPI application with Jinja2 templates and Tailwind CSS
- Docker Compose stack (PostgreSQL, Prefect server + worker, Redis)
- Alembic database migrations
- Test suite: domain, application, infrastructure, and API layers
- `mise` tasks for common development commands
- HSEL-1.0 license with ethical use restrictions

[202505191200]: https://github.com/oliverma/hazlo/releases/tag/202505191200