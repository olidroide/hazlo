# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **Versioning**: This project uses **timestamp-based versioning** (`YYYYMMDDHHMM`), NOT Semantic Versioning.
> Dev version is `0.0.0`. Releases use `mise run release`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## [Unreleased]

### Added

- **Pydantic AI integration (Phase 3 complete)**: Removed all legacy LLM infrastructure. Deleted `GeminiProvider`, `OpenRouterProvider`, `LLMProvider` ABC, `LLMClient`, `QualityClassifier`, and `LLMEnrichmentService` (~650 LOC). Admin routes now use pydantic-ai providers directly for `test_connection` and `list_models`. All LLM operations now use pydantic-ai agents with structured output.
- **Pydantic AI integration (Phase 2 complete)**: All production call sites now use pydantic-ai agents. `QualityClassifierAgent` and `LocationEnrichmentAgent` replace legacy `QualityClassifier` and `LLMEnrichmentService` in `flows.py` and `ingest_source.py`. Tests updated to use `FunctionModel` for mocking structured output. Legacy classes marked as deprecated.
- **Pydantic AI integration (Phase 1)**: Migrated LLM classification and location enrichment to pydantic-ai 1.102.0. `QualityClassifierAgent` and `LocationEnrichmentAgent` use structured output (`output_type`) with automatic validation and retries. `FallbackModel` handles provider failover (Gemini → OpenRouter). Legacy `LLMClient`/providers kept for admin routes.
- **LLM output models**: `ClassificationOutput` and `LocationEnrichmentOutput` Pydantic models in `domain/llm_output.py` for type-safe LLM responses.
- **Content hash deduplication**: Events deduplicated by SHA-256 content hash with normalization (whitespace, case, datetime). Upsert on `source_url` conflict.
- **Event detail view**: Full event detail page with LLM response section, confidence progress bar, publish button for approved events.

### Fixed

- **LLM JSON parsing**: `maxOutputTokens: 200` truncated Gemini responses. Increased to 500. Pydantic AI structured output eliminates manual JSON parsing.
- **Price display**: Show `amount_cents/100` correctly in euros.
- **Repository upsert bug**: `EventRepository.save()` and `SourceRepository.save()` used `session.add()` which fails on duplicate entities. Changed to `session.merge()` for upsert behavior.
- **LLM provider save**: `LLMProviderRepository.save()` used `session.add()`. Changed to `session.merge()` to allow provider updates.
- **Prefect deployment entrypoints**: `from_source().deploy()` corrupted module-path entrypoints to file paths. Fixed by using `client.create_deployment()` directly with explicit `entrypoint` parameter.
- **Docker DATABASE_URL**: `${DATABASE_URL:-...}` picked up host `.env` value. Changed to use shared `POSTGRES_*` variables for Docker-internal connections.
- **Docker build**: hatchling requires `README.md` in build context. Added `!README.md` to `.dockerignore`.
- **RSS date parsing**: ESMadrid schedules can use late-night times like `30:00 h`. The RSS adapter now rolls overflow hours into the next day and clamps invalid minutes instead of crashing ingestion.

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