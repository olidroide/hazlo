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
│   ├── source.py              # Source, SourceType, SourceStatus
│   ├── review.py              # Review, ReviewAction, InvalidTransitionError
│   ├── llm_provider.py        # LLMProvider entity (admin-configurable providers)
│   └── source_health.py       # SourceHealth entity (per-source metrics)
├── application/
│   ├── use_cases/             # Orchestrate services, no framework imports
│   │   ├── ingest_source.py   # IngestSource use case (adapter → enrich → dedup → classify → review)
│   │   └── review_event.py    # ReviewEvent use case
│   └── services/              # Deterministic + LLM services
│       ├── enrichment_service.py   # Normalize dates, prices, addresses, infer category
│       ├── dedup_service.py        # URL + title similarity dedup
│       ├── quality_classifier.py   # LLM: classify is_children, is_toddler, confidence
│       └── review_engine.py        # Rules: approve/reject/flag based on confidence
├── infrastructure/
│   ├── adapters/              # Source connectors (BaseSourceAdapter ABC)
│   ├── api/                   # FastAPI routes + schemas + deps
│   ├── db/                    # SQLAlchemy models + async repositories
│   ├── llm/                   # LLM provider implementations
│   │   ├── providers/         # GeminiProvider, OpenRouterProvider
│   │   ├── client.py          # Provider router + automatic fallback
│   │   └── prompts.py         # System prompts
│   ├── crypto.py              # Fernet encrypt/decrypt for API keys
│   ├── prefect/               # Scheduled flows + deployments
│   ├── static/                # CSS, JS, images
│   └── templates/             # Jinja2 + HTMX templates
├── main.py                    # FastAPI app entry point
└── settings.py                # Pydantic Settings (LLM config, threshold, secret key)
```

## Key Entities

### EventStatus State Machine

```
PENDING ──▶ APPROVED ──▶ PUBLISHED
   │            │
   └──────▶ REJECTED ◀────────┘
```

Allowed transitions (`ALLOWED_TRANSITIONS` in `domain/event.py`):
- PENDING → {APPROVED, REJECTED}
- APPROVED → {PUBLISHED, REJECTED}

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
- `QualityClassifier`: LLM classification via `LLMClient` → Gemini default, OpenRouter fallback
- `ReviewEngine`: rule-based approve/flag based on `confidence_score` vs `auto_approve_threshold`

**Idempotency** (`hazlo/domain/event.py`):
- `IdempotencyKey`: SHA-256 value object computed from source_url + normalized title + start_at
- `Event.compute_idempotency_key()`: generates deterministic key for exactly-once ingestion
- `EventRepository.list_existing_idempotency_keys()`: batch check before processing
- `IngestSource` skips events with existing keys, avoiding duplicate work

**LLM layer** (`hazlo/infrastructure/llm/`):
- `LLMClient`: provider router with automatic fallback and circuit breaker protection
- `GeminiProvider`: Google Gemini direct API (free tier, `responseMimeType: application/json`)
- `OpenRouterProvider`: OpenRouter gateway (fallback provider)
- `prompts.py`: system prompts for QualityClassifier (V1)

**Circuit Breaker** (`hazlo/domain/circuit_breaker.py`):
- Per-provider circuit breaker protecting against cascading LLM failures
- States: CLOSED → OPEN (after N consecutive failures) → HALF_OPEN (after timeout) → CLOSED
- `LLMClient.generate()` skips providers with OPEN circuits
- Configurable via `llm_circuit_breaker_failure_threshold` (default: 3) and `llm_circuit_breaker_reset_timeout_seconds` (default: 60)
- `LLMClient.circuit_metrics` exposes per-provider state and failure counts
- `LLMClient.reset_all_circuits()` for manual recovery

**LLM Evaluation** (planned): gold dataset, precision/recall metrics, prompt versioning, rollback criteria.
See `docs/agentic-system.md` → "LLM Evaluation" section.

**Pydantic AI** (future migration target): Partial adoption planned for `QualityClassifier` only.
See `.agents/skills/pydantic-ai-llm/SKILL.md` for architecture decision and implementation pattern.
Current direct Gemini implementation stays as fallback.

## HTTP Routes

| Method | Path | Handler | Returns |
|--------|------|---------|---------|
| GET | `/admin/sources` | `list_sources` | HTML source list |
| GET | `/admin/sources/_new` | `new_source_form` | HTML create form |
| POST | `/admin/sources` | `create_source` | HTML row (HTMX) |
| GET | `/admin/sources/{id}` | `get_source` | HTML detail |
| PATCH | `/admin/sources/{id}/toggle` | `toggle_source` | HTML row (HTMX) |
| GET | `/admin/events` | `list_events` | HTML event list (?status=) |
| GET | `/admin/events/{id}` | `get_event` | HTML event card |
| PATCH | `/admin/events/{id}/review` | `review_event` | HTML event card |
| GET | `/admin/events/{id}/audit` | `get_event_audit` | HTML audit trail |
| GET | `/admin/llm-providers` | `list_llm_providers` | HTML LLM provider list |
| GET | `/admin/llm-providers/_new` | `new_provider_form` | HTML create form |
| POST | `/admin/llm-providers` | `create_provider` | HTML row (HTMX) |
| POST | `/admin/llm-providers/{id}/test` | `test_provider_connection` | JSON {success: bool} |
| POST | `/admin/llm-providers/{id}/activate` | `activate_provider` | JSON {success: bool} |
| DELETE | `/admin/llm-providers/{id}` | `delete_provider` | JSON {success: bool} |
| GET | `/` | `root` | HTML base template |

All routes return server-rendered HTML. HTMX swaps partials (`_row.html`,
`_event_card.html`, `_audit_trail.html`).

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

## Python Conventions

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

## Repository Pattern — merge() vs add()

**Rule: Use `session.merge()` for upsert, `session.add()` for append-only.**

| Entity | Method | Why |
|--------|--------|-----|
| Event | `merge()` | Events can be re-ingested (same idempotency_key) |
| Source | `merge()` | Sources can be re-configured (same ID) |
| LLMProvider | `merge()` | Providers can be updated (same ID) |
| Review | `add()` | Reviews are append-only audit trail (never update) |
| ExtractionRun | `add()` | Runs are append-only history (never update) |

**Critical:** `session.merge()` is async — always `await self._session.merge(...)`.

**Bug pattern:** Using `add()` on an entity that already exists → `IntegrityError` on commit.
**Fix:** Use `merge()` for any entity that might be re-saved with the same primary key.

## Prefect Flows

| Flow | Schedule | File |
|------|----------|------|
| `ingest-all-sources` | Every 30 min | `infrastructure/prefect/flows.py` |
| `ingest-single-source` | Manual | `infrastructure/prefect/flows.py` |

Deployment config: `docker/prefect_init.py`

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
| `HAZLO_ENV` | `development` | `development` / `production` / `test` |
| `GEMINI_API_KEY` | `""` | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `LLM_TIMEOUT` | `30` | LLM call timeout (seconds) |
| `LLM_MAX_RETRIES` | `2` | Max retries on LLM failure |
| `AUTO_APPROVE_THRESHOLD` | `0.95` | Confidence threshold for auto-approve |
| `HAZLO_SECRET_KEY` | `""` | Fernet key for encrypting API keys |
| `LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `3` | Consecutive failures to open circuit |
| `LLM_CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` | `60.0` | Seconds before HALF_OPEN attempt |

Settings class: `hazlo/settings.py` (Pydantic BaseSettings).

## Docker Compose

| Service | Port | Purpose |
|---------|------|---------|
| postgres | 5433 | App + Prefect database |
| redis | — | Prefect broker |
| prefect-server | 4200 | Prefect UI + API |
| prefect-worker | — | Flow execution |

Init script creates `hazlo` and `prefect` databases.

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