# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

> **Versioning**: This project uses **timestamp-based versioning** (`YYYYMMDDHHMM`), NOT Semantic Versioning.
> Dev version is `0.0.0`. Releases use `mise run release`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## [Unreleased]

### Added

- **Two-phase ingestion (unified reparse)**: Split monolithic ingestion into `ingest_raw` (fetch + persist RAW to filesystem) and `parse_raw` (read stored RAW + normalize + enrich + save). Enables reparse from stored RAW without re-fetching source. Behind feature flag `HAZLO_UNIFIED_REPARSE`.
- **RAW filesystem storage**: `RawDocumentStore` protocol + `LocalFilesystemStore` implementation. Atomic writes (`.tmp` → rename + `fsync`), flat layout `{event_id}.raw.json`. Configurable for S3/R2 via `HAZLO_RAW_STORAGE_BACKEND`. Docker volume `raw-data` mounted at `/data/raw` for hazlo + prefect-worker.
- **Raw documents table**: Migration `e79067f213b6` adds `raw_documents` table (metadata-only: `event_id` FK, `content_hash`, `storage_uri`, `fetched_at`, `parsed_at`). Actual RAW data lives in filesystem.
- **ReparseEventAgent**: Unified LLM agent for reparsing events from stored RAW. Takes `raw_payload`, `raw_body`, `existing_event` → returns `ReparseEventOutput` with `field_confidence` dict. Uses pydantic-ai structured output.
- **ReparseEvent + EditEvent use cases**: `ReparseEvent` reads RAW, calls agent, computes delta, updates event + audit. `EditEvent` validates manual field changes, updates event + audit.
- **CSRF middleware**: Blocks all POST/PATCH/DELETE to `/admin/*` without valid token. Token via `X-CSRF-Token` header or form field `csrf_token`. Test fixture `_disable_csrf` for compatibility.
- **Rate limiter**: `RateLimiter` with sliding window. `reparse_limiter`: 5 calls/min per event, 30/hour per admin.
- **Event detail page (full)**: `event_detail.html` with read/edit modes, RAW section (collapsible), metadata, audit trail. Uses Atomic Design components. Routes: `GET /{id}`, `POST /{id}/edit`, `POST /{id}/reparse`.
- **Atomic Design components**: `components/` hierarchy — atoms (badge, confidence_bar, status_pill), molecules (field_row, raw_block), macros (reusable Jinja2 macros). Promotion rule: used ≥3 times.
- **Per-source Prefect deployment manager**: Added `source_deployment_manager.py` to reconcile one deployment per source (`source-{source_id}`), update interval schedules from `fetch_interval_minutes`, pause deployments when sources are inactive, delete deployments when sources are removed, and trigger `run-now` flow runs through Prefect API.
- **Source delete endpoint**: Added `DELETE /admin/sources/{id}` and UI action to remove a source and its Prefect deployment.

- **Pydantic AI integration (Phase 3 complete)**: Removed all legacy LLM infrastructure. Deleted `GeminiProvider`, `OpenRouterProvider`, `LLMProvider` ABC, `LLMClient`, `QualityClassifier`, and `LLMEnrichmentService` (~650 LOC). Admin routes now use pydantic-ai providers directly for `test_connection` and `list_models`. All LLM operations now use pydantic-ai agents with structured output.
- **Pydantic AI integration (Phase 2 complete)**: All production call sites now use pydantic-ai agents. `QualityClassifierAgent` and `LocationEnrichmentAgent` replace legacy `QualityClassifier` and `LLMEnrichmentService` in `flows.py` and `ingest_source.py`. Tests updated to use `FunctionModel` for mocking structured output. Legacy classes marked as deprecated.
- **Pydantic AI integration (Phase 1)**: Migrated LLM classification and location enrichment to pydantic-ai 1.102.0. `QualityClassifierAgent` and `LocationEnrichmentAgent` use structured output (`output_type`) with automatic validation and retries. `FallbackModel` handles provider failover (Gemini → OpenRouter). Legacy `LLMClient`/providers kept for admin routes.
- **LLM output models**: `ClassificationOutput` and `LocationEnrichmentOutput` Pydantic models in `domain/llm_output.py` for type-safe LLM responses.
- **Content hash deduplication**: Events deduplicated by SHA-256 content hash with normalization (whitespace, case, datetime). Upsert on `source_url` conflict.
- **Event detail view**: Full event detail page with LLM response section, confidence progress bar, publish button for approved events.
- **Ingestion runtime guardrails**: Added configurable Prefect timeouts to prevent indefinitely running ingestion jobs (`prefect_ingest_flow_timeout_seconds`, `prefect_fetch_source_task_timeout_seconds`).
- **RSS recency cap**: RSS adapter now processes only the most recent 30 feed items by default (`rss_max_results`) before normalization to reduce backlog and LLM load.
- **Ingestion observability logs**: Added detailed phase logs and timings (fetch, parse/select RSS, dedup preload, LLM infra boot, execute, persist, commit) plus traceback logging for fetch/normalize/task exceptions.

### Removed

- **Dead code cleanup**: Deleted 8 unused modules (`domain/llm_provider.py`, `domain/source_health.py`, `domain/circuit_breaker.py`, `application/services/source_health_service.py`, `infrastructure/api/schemas.py`, `infrastructure/llm/__init__.py`, `tests/domain/test_circuit_breaker.py`, `tests/application/test_source_health_service.py`). Removed `ingest_all_sources_flow` (never deployed). Dropped 5 dead Settings fields (`hazlo_env`, `ssl_cert_file`, `llm_circuit_breaker_*`, `prefect_server_analytics_enabled`). Removed 6 dead env vars from `.env.example` (`GEMINI_*`, `OPENROUTER_*`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`).
- **Redundant dependency**: Removed `pydantic-ai-slim[groq]` (full `pydantic-ai` already includes groq). Added explicit `cryptography>=42` dependency.
- **Dead column**: Dropped `extraction_runs.snapshot` (created in initial schema but never written or read).
- **NotImplementedError stubs**: Replaced with `AdapterNotImplementedError` for clearer error messages on unimplemented Web/Email adapters.

### Fixed

- **Scheduler contract mismatch**: Replaced legacy global `every-30-minutes`/`manual-trigger` deployment model with per-source reconciliation, so Prefect schedule now matches source capture interval configured in admin.
- **Run-now visibility**: `POST /admin/sources/{id}/run-now` now creates a Prefect flow run instead of executing ingestion inline, making on-demand executions visible in Prefect UI.

- **LLM active provider lookup**: `LLMProviderRepository.get_active()` no longer assumes a single active row. It now returns the active provider with the lowest `priority` (deterministic primary) so multiple active providers can coexist for fallback chains without `MultipleResultsFound` crashes.
- **HTMX boosted navigation**: Preserved admin shell (header/nav) during internal navigation by targeting boosted swaps to `#main-content` in `base.html` (`hx-target` + `hx-swap="innerHTML"`). Combined with dynamic base template selection (`base.html` vs `base_htmx.html`), hard refresh stays full-page while internal navigation updates only section content.
- **Sources detail navigation**: Hardened source detail links to use explicit HTMX container swaps (`hx-get` + `hx-target="#main-content"` + `hx-push-url="true"`) instead of inherited boost only, preventing header loss on `/admin/sources/{id}` transitions.
- **Admin navigation redirects**: Normalized admin links to canonical trailing-slash routes (`/admin/sources/`, `/admin/events/?status=...`, `/admin/llm-providers/`) to avoid extra `307 Temporary Redirect` round-trips.
- **LLM JSON parsing**: `maxOutputTokens: 200` truncated Gemini responses. Increased to 500. Pydantic AI structured output eliminates manual JSON parsing.
- **Price display**: Show `amount_cents/100` correctly in euros.
- **Repository upsert bug**: `EventRepository.save()` used `session.add()` which fails on duplicate entities. Replaced with PostgreSQL `INSERT ... ON CONFLICT (source_url) DO UPDATE` (with `session.merge()` fallback for SQLite tests).
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