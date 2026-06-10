# AI Context Guide

> This file is the **single entry point** for AI agents (Copilot, Claude Code, OpenCode, etc.)
> working on the Hazlo codebase. It provides everything needed to generate correct,
> idiomatic code in one dense, scannable document.

---

For human-oriented docs, see [README.md](../README.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

## Project Summary

**Hazlo** — Smart event agenda with human review. Ingests events from multiple sources,
normalizes them, and requires human approval before publishing. Built for cities and
communities that care about data quality.

## Architecture (MANDATORY)

Three layers, strict dependency direction:

```
domain/          → NO imports from application or infrastructure
application/     → imports from domain ONLY
infrastructure/  → imports from domain + application
```

**Never** import infrastructure from domain or application. If you need a repository
or adapter in a use case, receive it via constructor injection (port/adapter pattern).

```
hazlo/
├── domain/                    # Entities, value objects, enums, business rules
│   ├── event.py               # Event, EventStatus, Location, Price, TicketInfo
│   ├── source.py              # Source, SourceType
│   ├── review.py              # Review, ReviewAction, InvalidTransitionError
│   └── llm_output.py          # Pydantic models for LLM structured output
├── application/
│   ├── use_cases/             # Orchestrate services, no framework imports
│   │   ├── ingest_source.py   # IngestSource use case (adapter → enrich → dedup → classify → review)
│   │   └── review_event.py    # ReviewEvent use case
│   └── services/              # Deterministic services
│       ├── enrichment_service.py   # Normalize dates, prices, addresses, infer category
│       ├── dedup_service.py        # URL + title similarity dedup
│       └── review_engine.py        # Rules: approve/flag based on confidence
├── infrastructure/
│   ├── adapters/              # Source connectors (BaseSourceAdapter ABC)
│   ├── api/                   # FastAPI routes + deps
│   ├── db/                    # SQLAlchemy models + async repositories
│   ├── llm/                   # pydantic-ai agents + factory + prompts
│   │   ├── factory.py         # Build LLM infrastructure (fallback chain)
│   │   ├── agents/            # Pydantic AI agents (QualityClassifierAgent, LocationEnrichmentAgent, DateParserAgent)
│   │   └── prompts.py         # System prompts
│   ├── crypto.py              # Fernet encrypt/decrypt for API keys
│   ├── prefect/               # Scheduled flows + deployments
│   ├── static/                # CSS, JS, images
│   └── templates/             # Jinja2 + HTMX templates
├── main.py                    # FastAPI app entry point
└── settings.py                # Pydantic Settings (threshold, secret key, prefect URLs)
```

## Key Entities

### EventStatus State Machine

```
PENDING ──▶ APPROVED ──▶ PUBLISHED
   │
   └──────▶ REJECTED
```

Allowed transitions (`ALLOWED_TRANSITIONS` in `domain/event.py`):
- PENDING → {APPROVED, REJECTED}
- APPROVED → {PUBLISHED}

Invalid transitions raise `InvalidTransitionError`.

### Idempotency Key

Every event has an `idempotency_key` (SHA-256 hex) computed from:
- `source_url` (exact)
- `title` (lowercased, whitespace-collapsed, trimmed)
- `start_at` (ISO format)

Same event from same source always produces same key. The key is stored with a unique constraint in the DB. The `IngestSource` use case batch-checks keys before processing, skipping duplicates. This provides exactly-once semantics for event ingestion.

Computed via `event.compute_idempotency_key() → IdempotencyKey`.

### Source Types

`RSS` | `WEB` | `EMAIL` — each maps to a `BaseSourceAdapter` implementation.
See [Agentic System](./agentic-system.md) for the full agent pipeline design.

### Review Actions

`APPROVE` | `REJECT` | `EDIT` — every action creates a `Review` audit record with
a `changes` diff computed by `Review.compute_diff(before, after)`.

## Source Connector Pattern

Every connector must implement:

```python
class BaseSourceAdapter(ABC):
    async def fetch(self, source: Source) -> list[dict]: ...
    async def normalize(self, raw: dict) -> Event: ...
```

Lifecycle: adapter.fetch(source) → raw dicts → adapter.normalize(raw) → domain Event
→ save with status=PENDING

New connectors go in `infrastructure/adapters/`. Register in the adapter registry
where `IngestSource` is constructed.

## Agentic Pipeline (Implemented Phase 1)

See [docs/agentic-system.md](./agentic-system.md) for full design. Summary:

```
Source → Adapter (deterministic) → Idempotency Check → EnrichmentService → DedupService → QualityClassifier (LLM) → ReviewEngine (rules) → DB
```

**Implemented services** (`hazlo/application/services/`):
- `EnrichmentService`: normalize dates/prices/addresses, extract metro from lookup table, infer category from keywords
- `DedupService`: URL match + title token similarity (Jaccard), threshold 0.85
- `QualityClassifier`: LLM classification via pydantic-ai `QualityClassifierAgent` → structured output with `ClassificationOutput`
- `ReviewEngine`: rule-based approve/flag based on `confidence_score` vs `auto_approve_threshold`

**Idempotency** (`hazlo/domain/event.py`):
- `IdempotencyKey`: SHA-256 value object computed from source_url + normalized title + start_at
- `Event.compute_idempotency_key()`: generates deterministic key for exactly-once ingestion
- `EventRepository.list_existing_idempotency_keys()`: batch check before processing
- `IngestSource` skips events with existing keys, avoiding duplicate work

**LLM layer** (`hazlo/infrastructure/llm/`):
- `agents/quality_classifier.py`: `QualityClassifierAgent` — pydantic-ai Agent with `output_type=ClassificationOutput`
- `agents/location_enrichment.py`: `LocationEnrichmentAgent` — pydantic-ai Agent with `output_type=LocationEnrichmentOutput`
- `agents/date_parser.py`: `DateParserAgent` — pydantic-ai Agent with `output_type=DateParsingOutput`
- `prompts.py`: system prompts for QualityClassifier (V1), LocationEnrichment (V2), DateParsing (V1)
- `factory.py`: `build_llm_infrastructure()` creates pydantic-ai models + `FallbackModel` chain
- Admin routes use pydantic-ai providers directly for `test_connection` and `list_models`

**Fallback chain** (replaces circuit breaker): pydantic-ai `FallbackModel` handles provider rotation automatically. Multiple providers may be active simultaneously; `FallbackModel` tries them in priority order (lowest `priority` first). If a provider fails, the next one in the chain is tried automatically. No circuit state is tracked — failures are per-call.

**LLM Evaluation** (planned): gold dataset, precision/recall metrics, prompt versioning, rollback criteria.
See `docs/agentic-system.md` → "LLM Evaluation" section.

**Pydantic AI** (adopted, Phase 3 complete — legacy removed): All production call sites use pydantic-ai agents. `QualityClassifierAgent` and `LocationEnrichmentAgent` use pydantic-ai 1.102.0 with structured output (`output_type`), automatic retries, exception handling (returns fallback on failure), and `FallbackModel` for provider failover. Legacy `LLMClient`/`GeminiProvider`/`OpenRouterProvider`/`QualityClassifier`/`LLMEnrichmentService` removed (~650 LOC). Admin routes use pydantic-ai providers directly. `build_llm_infrastructure()` in `flows.py` creates pydantic-ai `GoogleModel`/`OpenRouterModel`/`GroqModel` + `FallbackModel`. Tests use `FunctionModel` to mock structured output responses.

**Active provider selection contract**: Multiple LLM providers may be active simultaneously for fallback chains. When a single "primary" active provider is required, repository lookups must be deterministic by `priority` (lowest value first), not `scalar_one_or_none()` over all active rows.

## HTTP Routes

| Method | Path | Handler | Returns |
|--------|------|---------|---------|
| GET | `/admin/sources/` | `list_sources` | HTML source list |
| GET | `/admin/sources/_new` | `new_source_form` | HTML create form |
| POST | `/admin/sources/` | `create_source` | HTML row (HTMX) |
| GET | `/admin/sources/{id}` | `get_source` | HTML detail |
| PATCH | `/admin/sources/{id}/toggle` | `toggle_source` | HTML row (HTMX) |
| POST | `/admin/sources/{id}/run-now` | `run_source_now` | HTML row (HTMX), triggers Prefect flow run |
| DELETE | `/admin/sources/{id}` | `delete_source` | Empty 200, deletes source + Prefect deployment |
| GET | `/admin/events/` | `list_events` | HTML event list (`?status=`) |
| GET | `/admin/events/{id}` | `get_event_detail_page` | HTML full event detail page |
| GET | `/admin/events/{id}/detail` | `get_event_detail` | HTML event detail (legacy, sidebar) |
| PATCH | `/admin/events/{id}/review` | `review_event` | HTML event card |
| GET | `/admin/events/{id}/audit` | `get_event_audit` | HTML audit trail |
| POST | `/admin/events/{id}/enrich` | `enrich_event` | HTML event card (LLM enrichment) |
| POST | `/admin/events/{id}/edit` | `edit_event` | HTML full event detail page (manual edit) |
| POST | `/admin/events/{id}/reparse` | `reparse_event` | HTML full event detail page (unified LLM reparse) |
| GET | `/admin/llm-providers/` | `list_llm_providers` | HTML LLM provider list |
| GET | `/admin/llm-providers/_new` | `new_provider_form` | HTML create form |
| POST | `/admin/llm-providers/models` | `list_provider_models` | HTML model list |
| POST | `/admin/llm-providers/` | `create_provider` | HTML row (HTMX) |
| POST | `/admin/llm-providers/{id}/test` | `test_provider_connection` | HTML test result |
| POST | `/admin/llm-providers/{id}/toggle-active` | `toggle_provider_active` | HTML row (HTMX) |
| DELETE | `/admin/llm-providers/{id}` | `delete_provider` | Empty 200 |
| GET | `/` | `root` | HTML base template |

All routes return server-rendered HTML. HTMX swaps partials (`_row.html`,
`_event_card.html`, `_audit_trail.html`).

For full-page admin templates, routing now selects base template by request type:
- `HX-Request: true` → `base_htmx.html` (content-only fragment for boosted navigation)
- regular browser request → `base.html` (full layout shell)

`base.html` sets `hx-target="#main-content"` + `hx-swap="innerHTML"` on `<body>`, so boosted navigation keeps header/nav and only replaces the main section container.

## HTMX + SSR Architecture Contract (MANDATORY)

This project uses a strict SSR-first architecture with HTMX as progressive enhancement.

### Design Rules

1. **Hard refresh must always render full page shell**
     - Full HTML document (`<html>`, `<head>`, nav, scripts) is rendered by Jinja template `base.html`.
2. **Internal navigation must only replace section content**
     - Boosted navigation swaps into `#main-content`, never the whole page body.
3. **Header/nav must remain persistent across internal navigation**
     - Shared shell elements stay outside `#main-content`.
4. **Server remains SSR source of truth**
     - HTMX consumes server-rendered fragments; no client-side SPA routing/state layer.

### Implementation Pattern

- `base.html` (full shell) includes:
    - `hx-boost="true"`
    - `hx-target="#main-content"`
    - `hx-swap="innerHTML"`
- Full-page templates use `{% extends base %}`.
- Route handlers pass `base=get_base(request)` and `get_base` selects:
    - `base.html` for non-HTMX requests
    - `base_htmx.html` for `HX-Request: true`

### Link and Endpoint Rules

- Use canonical trailing-slash routes for list pages:
    - `/admin/sources/`, `/admin/events/?status=...`, `/admin/llm-providers/`
- Avoid 307 redirects in navigation paths.
- For known fragile transitions (for example source-list to source-detail), prefer explicit HTMX attributes on links:
    - `hx-get`, `hx-target="#main-content"`, `hx-swap="innerHTML"`, `hx-push-url="true"`.

### Regression Checklist

- Hard refresh on any admin page keeps full shell.
- Boosted navigation does not remove/recreate header/nav.
- HTMX responses for full-page routes do not include `<html>/<head>/<body>/<nav>`.
- No unexpected 307 redirects in admin navigation.

## Tooling Commands

```bash
mise run dev              # Start FastAPI dev server
mise run test             # Run pytest
mise run lint             # Ruff linter
mise run fmt              # Ruff formatter
mise run typecheck        # ty strict mode
mise run migrate          # Alembic migrations
mise run prefect-server   # Prefect server
mise run prefect-worker   # Prefect worker
mise run deploy-flows     # Deploy Prefect flows
```

## Ingestion Guardrails

- Prefect ingestion has runtime limits to avoid stuck runs piling up:
    - `prefect_ingest_flow_timeout_seconds` (default: `1500`)
    - `prefect_fetch_source_task_timeout_seconds` (default: `1200`)
- RSS ingestion applies an early recency cap before normalization/LLM stages:
    - `rss_max_results` (default: `30` most recent services)
- Ingestion emits detailed runtime logs for debugging:
  - step-level events (`source_loaded`, `fetch_start`, `fetch_done`, `normalize`, `llm_*`, `complete`)
  - phase timings for task orchestration (dedup preload, LLM infra setup, execute, persist, commit)
  - stack traces for fetch/normalize and gathered task exceptions

- **Line length**: 120
- **Formatter**: Ruff (isort-compatible import sorting)
- **Linter**: Ruff with `[E, F, I, N, W, UP, B, SIM, RUF]`
- **Type checker**: ty strict mode
- **Type annotations**: Required on all function signatures
- **No comments** unless they explain *why*, not *what*
- **Dataclasses** for domain entities (mutable), frozen dataclasses for value objects
- **Async everywhere** in infrastructure (asyncpg, async SQLAlchemy, async FastAPI)
- **Pydantic Settings** for configuration (`settings.py`)

## Testing Conventions

- `tests/domain/` — pure business logic, synchronous, no I/O
- `tests/application/` — use cases with mock repos/adapters
- `tests/infrastructure/` — Testcontainers PostgreSQL, mocked HTTP
- `tests/api/` — FastAPI TestClient with dependency overrides
- `asyncio_mode = "auto"` in pytest config
- Factory Boy for test data

### Testing Strategy — Mocks vs Testcontainers

**Use mocks for:**
- Unit tests for pure business logic (domain layer)
- API route tests that don't touch real DB
- LLM provider tests (mock HTTP responses)

**Use Testcontainers for:**
- Repository tests (real PostgreSQL, real SQL)
- Integration tests (full ingestion → review → publish flows)
- Any test that exercises SQLAlchemy queries/merges

**Critical:** API tests with mocked repositories won't catch `session.add()` vs `session.merge()` bugs. Always add Testcontainers integration tests for repository `save()` methods.

### TDD Enforcement

Pre-commit hook (`.githooks/pre-commit`) blocks commits where `hazlo/*.py` files change but `tests/*.py` files do not. Exceptions: `__init__.py`, `templates/`, `static/`, `docker/`, `alembic/`.

Emergency bypass: `git commit --no-verify` (requires justification in commit message).

## Repository Pattern — upsert vs add()

**Rule: Use PG `ON CONFLICT DO UPDATE` for upsert, `session.add()` for append-only.**

| Entity | Method | Why |
|--------|--------|-----|
| Event | `INSERT ... ON CONFLICT (source_url) DO UPDATE` | Events can be re-ingested (same source_url); SQLite fallback uses `merge()` |
| Source | `merge()` | Sources can be re-configured (same ID) |
| LLMProvider | `merge()` | Providers can be updated (same ID) |
| Review | `add()` | Reviews are append-only audit trail (never update) |
| ExtractionRun | `add()` | Runs are append-only history (never update) |

**Critical:** `session.merge()` is async — always `await self._session.merge(...)`.

**Bug pattern:** Using `add()` on an entity that already exists → `IntegrityError` on commit.
**Fix:** Use `merge()` for any entity that might be re-saved with the same primary key.

## Two-Phase Ingestion (Unified Reparse)

### Architecture

Two separate Prefect flows replace the monolithic ingestion pipeline for reparse scenarios:

```
Phase 1: ingest_raw  →  fetch RAW (payload + body)  →  persist to filesystem
Phase 2: parse_raw   →  read stored RAW  →  normalize  →  enrich  →  save to DB
```

**Why two phases:**
- RAW data stored once, re-parseable without re-fetching source
- Enables manual edit + AI reparse from same RAW snapshot
- Decouples fetch failures from parse failures
- Future: can reparse with improved prompts without hitting source again

### RAW Storage

**Protocol:** `RawDocumentStore` (`hazlo/domain/ports/raw_document_store.py`)
- `write(event_id, content) → str` (returns URI)
- `read(event_id) → bytes`
- `exists(event_id) → bool`
- `delete(event_id) → None`
- `get_uri(event_id) → str`

**Implementation:** `LocalFilesystemStore` (`hazlo/infrastructure/storage/local_filesystem.py`)
- Atomic write: `.tmp` file → `os.rename()` with `os.fsync()`
- Flat layout: `{raw_local_path}/{event_id}.raw.json`
- File content: JSON with `raw_payload`, `raw_body`, `fetched_at`, `content_hash`

**Factory:** `build_raw_document_store(settings)` → returns `LocalFilesystemStore` by default
- Configurable for S3/R2 via `HAZLO_RAW_STORAGE_BACKEND` setting
- `HAZLO_RAW_LOCAL_PATH` defaults to `./data/raw`

### Database: `raw_documents` Table

Metadata-only table (`alembic/versions/e79067f213b6_add_raw_documents_table.py`):
- `id` (UUID PK), `event_id` (FK → events.id ON DELETE CASCADE)
- `content_hash` (SHA-256 of raw content), `fetched_at` (UTC)
- `storage_uri` (filesystem path or S3 key), `parsed_at` (nullable)
- `created_at`, `updated_at`

Actual RAW data lives in filesystem, not DB. `RawDocumentModel` is metadata + FK.

### Reparse Flow

1. Admin clicks "Reparse" on event detail page → `POST /admin/events/{id}/reparse`
2. CSRF validation + rate limit check (5/min per event, 30/hour per admin)
3. `ReparseEvent` use case:
   - Reads RAW from filesystem via `RawDocumentStore`
   - Calls `ReparseEventAgent` with `raw_payload`, `raw_body`, `existing_event`
   - Agent returns `ReparseEventOutput` with `field_confidence` dict
   - Computes delta between existing event and new parsed data
   - Updates event fields, creates `Review` audit record
4. Returns updated event detail page with changes highlighted

### Edit Flow

1. Admin clicks "Edit" on event detail page → switches to edit mode
2. Manual field changes → `POST /admin/events/{id}/edit`
3. `EditEvent` use case with `EditEventCommand`:
   - Validates field changes
   - Updates event, creates `Review` audit record with diff
4. Returns updated event detail page

### LLM Agent: `ReparseEventAgent`

- Unified prompt (`REPARSE_EVENT_V1`) takes raw payload + body + existing event
- Returns `ReparseEventOutput` with all event fields + `field_confidence` dict
- `field_confidence` maps field name → confidence score (0.0-1.0)
- Uses pydantic-ai structured output (`output_type=ReparseEventOutput`)
- Behind feature flag `HAZLO_UNIFIED_REPARSE` (default `false`)

### Event Detail Page

**Template:** `hazlo/infrastructure/templates/admin/events/event_detail.html`
- Two modes: read mode (default) + edit mode (after clicking "Edit")
- Sections: metadata header, event fields (editable in edit mode), RAW section (collapsible), audit trail
- Uses Atomic Design components from `components/`
- CSRF token in edit/reparse forms
- Rate limit error shown if reparse limit exceeded

### Components (`hazlo/infrastructure/templates/components/`)

Atomic Design hierarchy: atoms → molecules → macros

**Atoms:**
- `badge/status.html` — status badge with color (pending/approved/rejected/published)
- `badge/confidence.html` — confidence badge (high/medium/low)
- `confidence_bar.html` — visual confidence bar (0-100%)
- `status_pill.html` — compact status indicator

**Molecules:**
- `field_row.html` — label + value pair (editable in edit mode)
- `raw_block.html` — collapsible RAW JSON viewer with syntax highlighting

**Macros:**
- `macros.html` — reusable Jinja2 macros for common patterns

**Promotion rule:** component promoted to `components/` when used ≥3 times across templates.

### CSRF Middleware

**File:** `hazlo/infrastructure/api/middleware/csrf.py`
- Blocks all POST/PATCH/DELETE to `/admin/*` without valid CSRF token
- Token checked via `X-CSRF-Token` header or form field `csrf_token`
- Token bound to session, validated against secret key
- `generate_csrf_token(session, secret_key)` → token string
- Test fixture `_disable_csrf` removes middleware from `app.user_middleware` for existing tests

### Rate Limiter

**File:** `hazlo/infrastructure/api/middleware/rate_limiter.py`
- `RateLimiter` class with sliding window
- `reparse_limiter` instance: 5 calls/min per event, 30/hour per admin
- In-memory dict keyed by `(user_id, event_id)` with timestamps
- Raises `RateLimitExceeded` when limit hit

## Prefect Flows

| Flow | Schedule | File |
|------|----------|------|
| `ingest-single-source` | Per source (`fetch_interval_minutes`) | `infrastructure/prefect/flows.py` |

Deployment reconciliation: `docker/prefect_init.py` + `infrastructure/prefect/source_deployment_manager.py`

Deployment naming convention:
- `source-{source_id}` for each source
- source active: deployment unpaused with source interval
- source inactive: deployment paused
- source deleted: deployment deleted

Flows orchestrate use cases. Never put business logic in Prefect flows.

### Prefect Deployment — Entrypoint Bug

**Problem:** `from_source().deploy()` with dotted module path (`hazlo.infrastructure.prefect.flows.func`) stores a file-path entrypoint (`../usr/local/lib/.../flows.py:func`) in the deployment. Worker can't find the flow.

**Solution:** Use `client.create_deployment()` directly with explicit `entrypoint` parameter:

```python
await client.create_deployment(
    flow_id=flow_id,
    name="deployment-name",
    entrypoint="hazlo.infrastructure.prefect.flows.flow_function_name",
    path="/usr/local/lib/python3.13/site-packages/hazlo/infrastructure/prefect",
    work_pool_name="local-pool",
    pull_steps=[],
    paused=False,
)
```

**Cleanup:** Always delete old deployments before re-deploying to avoid stale entrypoints.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://hazlo:hazlo@localhost:5433/hazlo` | PostgreSQL async connection |
| `AUTO_APPROVE_THRESHOLD` | `0.95` | Confidence threshold for auto-approve |
| `HAZLO_SECRET_KEY` | `""` | Fernet key for encrypting API keys |
| `VERIFY_SSL` | `true` | SSL verification for outbound HTTP requests |
| `CA_BUNDLE` | `None` | Path to corporate CA bundle (behind proxy) |
| `PREFECT_API_URL` | `http://localhost:4200/api` | Prefect API base URL for app + worker reconciliation |
| `PREFECT_WORK_POOL_NAME` | `local-pool` | Prefect work pool for per-source deployments |
| `PREFECT_INGEST_FLOW_TIMEOUT_SECONDS` | `1500` | Prefect flow timeout (seconds) |
| `PREFECT_FETCH_SOURCE_TASK_TIMEOUT_SECONDS` | `1200` | Prefect task timeout (seconds) |
| `RSS_MAX_RESULTS` | `30` | Max results per RSS fetch |
| `HAZLO_RAW_STORAGE_BACKEND` | `local` | RAW storage backend (`local` or `s3`) |
| `HAZLO_RAW_LOCAL_PATH` | `./data/raw` | Local filesystem path for RAW storage |
| `HAZLO_UNIFIED_REPARSE` | `false` | Enable unified reparse feature flag |

LLM provider API keys are configured via `/admin/llm-providers` (encrypted in DB), not via env vars.

Settings class: `hazlo/settings.py` (Pydantic BaseSettings).

## Docker Compose

| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5433 | App + Prefect database |
| redis | 6380 | Reserved for future caching (not currently used) |
| hazlo | 8000 | FastAPI app (with `raw-data` volume mounted at `/data/raw`) |
| prefect-server | 4200 | Prefect UI + API |
| prefect-worker | — | Flow execution (shares `raw-data` volume with hazlo) |

**Volumes:**
- `postgres_data` — PostgreSQL data persistence
- `redis_data` — Redis data persistence
- `raw-data` — RAW event data storage (filesystem backend)

Init script creates `prefect` database; `hazlo` database is created from `POSTGRES_DB` env var.

## Versioning

This project uses **timestamp-based versioning**, NOT Semantic Versioning.

- **Dev**: `__version__ = "0.0.0"` in `hazlo/__init__.py` — don't touch it during development
- **Release**: automatic on merge to `main`. CI generates `YYYYMMDDHHMM`, updates `__init__.py`, commits, tags, creates GitHub Release
- **Manual**: `mise run release` for local releases (use sparingly; prefer CI)
- **Check**: `mise run version`
- CHANGELOG entries use `YYYYMMDDHHMM` format
- **Never** use semver tags (`v1.2.3`)

## Branching

- `dev` — daily development, all PRs target this branch
- `main` — releases only. Merge `dev` → `main` triggers auto-release

**Release flow**: PR `dev` → `main` → merge → CI auto-releases (commit + tag + GitHub Release).

## NEVER

- Import from `infrastructure` in `domain` or `application`
- Put business logic in Prefect flows
- Add framework imports (FastAPI, SQLAlchemy) to domain or application layers
- Commit `.env` files or secrets — always `.gitignore`
- Skip type annotations on function signatures
- Use synchronous DB calls — always async
- Change code without updating documentation (see below)
- Hardcode credentials, tokens, or API keys — use environment variables
- Use `eval()`, `exec()`, `pickle`, or `subprocess` with untrusted input
- Disable Ruff security rules (S-prefixed) without a justified reason
- Use `SELECT *` in SQL — always specify columns explicitly

## Documentation (MANDATORY)

Documentation is not optional. This is an open-source project — docs are the first impression.

**Every code change that affects behavior MUST update documentation.** Before finishing any task:

| If you changed... | Update this file |
|---|---|
| Entities, routes, conventions, tooling, architecture | `docs/ai-context.md` |
| Setup steps, tech stack, features visible to new users | `README.md` |
| Added, changed, or removed a feature | `CHANGELOG.md` |
| Dev workflow, conventions, versioning rules | `CONTRIBUTING.md` |

When in doubt, update. Stale docs are worse than no docs.

## Related Files

| File | Content |
|------|---------|
| [README.md](../README.md) | Project overview, setup, architecture, roadmap |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, conventions, PR process, versioning rules |
| [CHANGELOG.md](../CHANGELOG.md) | Release history (timestamp format) |
| [LICENSE](../LICENSE) | HSEL-1.0 license |
| [ETHICAL-USE.md](../ETHICAL-USE.md) | Ethical use restrictions |
| [.github/copilot-instructions.md](../.github/copilot-instructions.md) | Copilot workspace instructions (points here) |
| [.agents/AGENTS.md](../.agents/AGENTS.md) | OpenCode agent instructions (points here) |