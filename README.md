<p align="center">
  <h1 align="center">Hazlo</h1>
  <p align="center">
    <strong>Smart event agenda with human review and source administration</strong>
  </p>
  <p align="center">
    Discover, normalize, and review events from multiple sources before showing them to your users.
  </p>
  <p align="center">
    <a href="#getting-started">Getting Started</a>
    &middot;
    <a href="#architecture">Architecture</a>
    &middot;
    <a href="#human-review-flow">Review Flow</a>
    &middot;
    <a href="CONTRIBUTING.md">Contributing</a>
  </p>
</p>

---

[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: HSEL-1.0](https://img.shields.io/badge/License-HSEL--1.0-blueviolet)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)

---

## About

**hazlo** is an event agenda designed for modern cities, focused on data quality and
human editorial control. It aggregates events from multiple sources, normalizes and
enriches them, and lets a person review each event before it becomes visible to the
public — ensuring accurate, trustworthy event listings.

### Why "hazlo"?

*Hazlo* means "do it" in Spanish — a call to action. The project empowers communities
to curate high-quality event data, bridging the gap between automated data collection
and human editorial judgment.

## Key Features

- **Multi-source ingestion** — RSS adapter implemented; Web and Email stubs planned
- **Source administration panel** — Add, verify, configure, and trigger extractions on demand
- **Event normalization** — All sources mapped to a common data model
- **Event enrichment** — Auto-classify children's activities and toddler-friendly events via LLM
- **Human-in-the-loop review** — Approve, edit, or reject events before publishing
- **LLM provider management** — Configure Gemini, OpenRouter, and Groq providers with admin UI
- **Fallback chain** — Multi-provider LLM calls with automatic fallback (pydantic-ai FallbackModel)
- **Full traceability** — Track extraction origin, timestamps, and manual review changes
- **Scheduled ingestion** — Prefect-powered per-source deployments using each source capture interval
- **SSE test integration** — Real-time log streaming for source pipeline testing

## Architecture

hazlo follows **DDD & Clean Architecture** principles, clearly separating layers:

```
hazlo/
├── domain/                     # Entities, value objects, business rules
│   ├── event.py                # Event, Location, Price, TicketInfo, EventStatus
│   ├── source.py               # Source, SourceType
│   ├── review.py               # Review, ReviewAction
│   └── llm_output.py           # Pydantic LLM output schemas
├── application/                # Use cases + domain services
│   ├── use_cases/
│   │   ├── ingest_source.py         # IngestSource
│   │   └── review_event.py          # ReviewEvent
│   └── services/
│       ├── enrichment_service.py    # Normalize dates, prices, addresses
│       ├── review_engine.py         # Auto-approve/flag based on confidence
│       └── dedup_service.py         # Duplicate detection via URL + title similarity
├── infrastructure/             # Frameworks, DB, API, adapters
│   ├── adapters/               # Source connectors (RSS implemented, Web/Email stubs)
│   │   ├── base.py             # BaseSourceAdapter interface
│   │   ├── rss_adapter.py
│   │   ├── web_adapter.py
│   │   └── email_adapter.py
│   ├── api/                    # FastAPI routes + Jinja2 templates
│   │   └── routes/
│   │       ├── admin_sources.py
│   │       ├── admin_events.py
│   │       └── admin_llm_providers.py
│   ├── db/                     # SQLAlchemy models + repositories
│   ├── llm/                    # pydantic-ai agents + factory + prompts
│   │   ├── factory.py          # Build LLM infrastructure (fallback chain)
│   │   ├── prompts.py          # System prompts for agents
│   │   └── agents/
│   │       ├── quality_classifier.py
│   │       ├── location_enrichment.py
│   │       └── date_parser.py
│   ├── prefect/                # Scheduled flows + per-source deployments
│   └── templates/              # Jinja2 + HTMX templates
├── static/                     # Tailwind CSS (input.css + compiled output.css)
└── main.py                     # FastAPI app entry point
```

| Layer | Responsibility | Dependencies |
|-------|---------------|-------------|
| **Domain** | Business entities, value objects, rules | None (pure Python) |
| **Application** | Use cases, domain services | Domain only |
| **Infrastructure** | DB, HTTP, adapters, scheduler | Domain + Application |

## Tech Stack

| Category | Technology |
|----------|------------|
| **Language** | Python 3.13+ |
| **API & Web** | FastAPI (HTTP API + server-side views) |
| **Validation** | Pydantic v2 |
| **ORM** | SQLAlchemy 2.x async + PostgreSQL |
| **Frontend** | HTMX + Jinja2 + Tailwind CSS v4 |
| **LLM** | pydantic-ai agents (Gemini, OpenRouter, Groq) with encrypted API key storage |
| **Scheduling** | Prefect 3.x |
| **Type Checking** | ty |
| **Linting & Formatting** | Ruff |
| **Package Manager** | uv |
| **Tool Manager** | mise |
| **Testing** | pytest + Testcontainers |
| **Infrastructure** | Docker + Docker Compose |

## Event Data Model

Each event is normalized to a common model:

| Field | Description |
|-------|-------------|
| `title` | Event name |
| `location` | Address, neighborhood, nearest metro stop |
| `start_at` / `end_at` | Start and end timestamps |
| `price` | Amount in cents, free/discount info |
| `ticket_info` | URL or point of sale (required if paid) |
| `is_children_activity` | Auto-classified children's activity flag |
| `is_toddler_friendly` | Auto-classified toddler-friendly flag |
| `confidence_score` | LLM classification confidence (0.0–1.0) |
| `agent_review` | LLM review metadata (raw response, reasoning) |
| `source_url` | Original source URL |
| `idempotency_key` | Deduplication key (source URL + title + start_at hash) |
| `status` | `pending` → `approved` → `published` (rejected and published are terminal) |

## Source Administration Panel

| View | Capabilities |
|------|-------------|
| **Source list** | Name, type, status, last run result, on-demand extraction |
| **Source detail** | Parsing config, extraction frequency, raw/normalized data preview |
| **Extraction history** | Run timestamps, new/updated counts, error debug messages |
| **Test integration** | SSE live log streaming for full pipeline testing |

**Routes:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/sources` | List all sources |
| `POST` | `/admin/sources` | Create a new source |
| `GET` | `/admin/sources/{id}` | Source detail + health + history |
| `PATCH` | `/admin/sources/{id}/toggle` | Activate/deactivate source |
| `DELETE` | `/admin/sources/{id}` | Delete source and remove its Prefect deployment |
| `POST` | `/admin/sources/{id}/run-now` | Trigger on-demand extraction |
| `POST` | `/admin/sources/{id}/test-connection` | Test source connectivity |
| `POST` | `/admin/sources/{id}/preview` | Preview parsed events |
| `GET` | `/admin/sources/{id}/test/stream` | SSE live test pipeline log |

## Human Review Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌───────────┐
│  Ingest  │────▶│  Review  │────▶│ Approve  │────▶│ Published │
│ (auto)   │     │ (human)  │     │ (human)  │     │  (public) │
└──────────┘     └──────────┘     └──────────┘     └───────────┘
                       │
                       ▼
                 ┌──────────┐
                 │ Rejected │
                 └──────────┘
```

1. **Ingestion** — System extracts from sources; events created as `pending`
2. **Classification** — LLM auto-classifies events (children's activity, toddler-friendly)
3. **Auto-approve** — High-confidence events auto-approved (threshold: 0.95)
4. **Review** — Human verifies flagged events; can approve, edit, or reject
5. **Audit** — Full record of who reviewed what, when, and what changed

**Review routes:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/events?status=pending` | Review queue |
| `GET` | `/admin/events/{id}` | Event detail card |
| `PATCH` | `/admin/events/{id}/review` | Approve/reject/edit event |
| `GET` | `/admin/events/{id}/audit` | Audit trail for an event |

## LLM Provider Admin

Manage LLM API keys and model selection via the admin panel at `/admin/llm-providers`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/llm-providers` | List configured providers |
| `POST` | `/admin/llm-providers` | Add a new provider (encrypted API key) |
| `POST` | `/admin/llm-providers/models` | Fetch available models from provider API |
| `POST` | `/admin/llm-providers/{id}/test` | Test provider connection |
| `POST` | `/admin/llm-providers/{id}/toggle-active` | Toggle provider active/inactive |
| `DELETE` | `/admin/llm-providers/{id}` | Remove provider (empty 200 response) |

API keys are encrypted at rest using Fernet symmetric encryption
with `HAZLO_SECRET_KEY`. pydantic-ai `FallbackModel` handles provider rotation
automatically based on priority ordering.

## Getting Started

### Prerequisites

- [Python 3.13+](https://www.python.org/)
- [mise](https://mise.jdx.dev/) — tool version manager and task runner
- [uv](https://docs.astral.sh/uv/) — package manager
- [Docker](https://www.docker.com/) — for PostgreSQL, Redis, and Prefect

### Quick Start

1. **Install mise and uv**

   ```bash
   curl https://mise.run | sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and set up the project**

   ```bash
   git clone https://github.com/oliverma/hazlo.git
   cd hazlo
   mise install          # install Python + tools from .mise.toml
   uv venv && source .venv/bin/activate
   uv sync               # install dependencies
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

   Key variables (see [`.env.example`](.env.example)):

    | Variable | Default | Description |
    |----------|---------|-------------|
    | `DATABASE_URL` | `postgresql+asyncpg://hazlo:hazlo@localhost:5433/hazlo` | PostgreSQL connection |
    | `HAZLO_SECRET_KEY` | — | Fernet key for encrypting LLM API keys (required) |
    | `ADMIN_USER` / `ADMIN_PASSWORD` | `admin` / — | Basic auth credentials for admin panel |
    | `AUTO_APPROVE_THRESHOLD` | `0.95` | Confidence threshold for auto-approval |
    | `PREFECT_API_URL` | `http://localhost:4200/api` | Prefect API URL used by app + worker |
    | `PREFECT_WORK_POOL_NAME` | `local-pool` | Prefect work pool for source deployments |
    | `VERIFY_SSL` | `true` | SSL verification for outbound HTTP requests |
    | `CA_BUNDLE` | — | Path to corporate CA bundle (behind proxy) |
    | `HAZLO_AUTO_MIGRATE` | `1` | Run Alembic migrations on startup (set `0` to disable) |

4. **Start infrastructure**

   ```bash
   docker compose up -d
   ```

   On startup, the hazlo container auto-runs database migrations. The
   prefect-worker container creates the `local-pool` work pool, removes legacy
   global deployments, and reconciles one Prefect deployment per source.

5. **Start the server**

   ```bash
   mise run dev        # migrations auto-run on startup
   ```

6. **Verify**

   - Admin panel: <http://127.0.0.1:8000/admin/sources>
   - Event review: <http://127.0.0.1:8000/admin/events?status=pending>
   - LLM providers: <http://127.0.0.1:8000/admin/llm-providers>
   - Prefect UI: <http://localhost:4200>

### Running with Docker Compose

```bash
docker compose up -d
```

All services auto-configure:

| Service | Role |
|---------|------|
| `postgres` | Database (PostgreSQL 14, port 5433 on host) |
| `redis` | Reserved for future caching (not currently used) |
| `hazlo` | FastAPI app (port 8000) — runs migrations on entry |
| `prefect-server` | Prefect API + UI (port 4200) |
| `prefect-worker` | Executes scheduled and on-demand ingest flows |

### Prefect

| URL / Command | Description |
|---------------|-------------|
| <http://localhost:4200> | Prefect UI dashboard |
| `mise run deploy-flows` | Re-deploy flows after code changes |
| `bash scripts/setup-prefect.sh` | Manual local Prefect setup (outside Docker) |

**Deployed flows:**

| Flow | Schedule | Description |
|------|----------|-------------|
| `ingest-single-source` | Per source (`fetch_interval_minutes`) | Ingest from one source deployment (`source-{source_id}`) |

## Developer Workflow

| Task | Command | Description |
|------|---------|-------------|
| `dev` | `mise run dev` | Start FastAPI (migrations run on startup) |
| `test` | `mise run test` | Run the full test suite |
| `lint` | `mise run lint` | Lint with Ruff |
| `fmt` | `mise run fmt` | Format with Ruff |
| `typecheck` | `mise run typecheck` | Type-check with ty |
| `migrate` | `mise run migrate` | Run Alembic migrations manually |
| `deploy-flows` | `mise run deploy-flows` | Re-deploy Prefect flows |

## Tailwind CSS

Tailwind CSS v4 is compiled from `hazlo/static/css/input.css`:

```bash
npm install                              # install Tailwind CLI
mise run tailwind-build                  # compile to output.css (one-shot)
mise run tailwind-watch                  # watch mode for development
```

The compiled `output.css` is gitignored — it's a build artifact regenerated on deploy.

## Testing

```bash
mise run test           # full suite
mise run test -- -k "test_event"   # specific test
mise run test -- --cov  # with coverage
```

Test structure mirrors the architecture:

| Directory | Scope |
|-----------|-------|
| `tests/domain/` | Business rules: event transitions, content hash, idempotency key |
| `tests/application/` | Use cases: ingestion, review, flow wiring |
| `tests/infrastructure/` | Adapters, LLM providers, crypto, repositories |
| `tests/api/` | HTTP endpoints (admin sources, events, LLM providers) |

### Testing conventions

- **Domain tests** — pure business logic, no I/O, no frameworks
- **Infrastructure tests** — PostgreSQL via Testcontainers; mocked external responses
- **Integration tests** — full ingestion → review → publishing flows
- **Pytest config** — `asyncio_mode = "auto"` in `pyproject.toml`

## Project Structure

```
hazlo/
├── hazlo/                          # Application source
│   ├── domain/                     # Domain layer (pure business logic)
│   │   ├── event.py                # Event entity + value objects
│   │   ├── source.py               # Source entity
│   │   ├── review.py               # Review + audit trail
│   │   └── llm_output.py           # Pydantic LLM output schemas
│   ├── application/                # Application layer (use cases + services)
│   │   ├── use_cases/
│   │   │   ├── ingest_source.py
│   │   │   └── review_event.py
│   │   └── services/
│   │       ├── enrichment_service.py
│   │       ├── review_engine.py
│   │       └── dedup_service.py
│   ├── infrastructure/             # Infrastructure layer
│   │   ├── adapters/               # Source connectors
│   │   │   ├── base.py
│   │   │   ├── rss_adapter.py
│   │   │   ├── web_adapter.py      # stub
│   │   │   └── email_adapter.py    # stub
│   │   ├── api/                    # FastAPI routes + deps
│   │   │   └── routes/
│   │   │       ├── admin_sources.py
│   │   │       ├── admin_events.py
│   │   │       └── admin_llm_providers.py
│   │   ├── db/                     # SQLAlchemy models + repositories
│   │   ├── llm/                    # pydantic-ai agents + factory
│   │   │   ├── factory.py
│   │   │   ├── prompts.py
│   │   │   └── agents/
│   │   │       ├── quality_classifier.py
│   │   │       ├── location_enrichment.py
│   │   │       └── date_parser.py
│   │   ├── prefect/                # Scheduled flows + deployments
│   │   │   ├── flows.py
│   │   │   └── deployments.py
│   │   └── templates/              # Jinja2 + HTMX templates
│   ├── static/                     # Tailwind CSS (input.css)
│   └── main.py                     # FastAPI app entry point
```

## Roadmap

- [ ] Advanced agenda filtering (neighborhood, type, price, family-friendliness)
- [ ] Notifications (email/push) for relevant new events
- [ ] Role-based access (source admin, event reviewer, read-only)
- [ ] Public API to expose events to third parties
- [ ] Metrics and quality reports per source

## Contributing

We welcome contributions! Please read the [Contributing Guide](CONTRIBUTING.md) for details on:

- Opening issues and feature requests
- Code style and architecture conventions
- Testing requirements
- Pull request process

## Troubleshooting

### Docker build fails: "README.md not found"

hatchling requires `README.md` in the build context. Ensure `.dockerignore` has `!README.md` to un-exclude it.

### Prefect schedules look wrong for a source

Per-source schedules are reconciled by `docker/prefect_init.py` at worker start. Re-run `docker compose up -d` to trigger reconciliation if the deployment interval in Prefect does not match `fetch_interval_minutes`.

### Database connection errors in Docker

If `DATABASE_URL` is set in your host `.env`, Docker Compose may pick it up instead of using the internal `postgres:5432` address. Use explicit `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` variables instead.

### IntegrityError on event save

Events use PostgreSQL `INSERT ... ON CONFLICT (source_url) DO UPDATE` for upsert.
If you see `IntegrityError`, check that unique constraints (`source_url`, `idempotency_key`, `content_hash`) are not violated by test data.

### LLM classification slow or failing

- 1000+ events with LLM calls = ~30 minutes. Consider batch processing.
- pydantic-ai structured output guarantees valid responses — no manual JSON parsing needed.
- Check provider status at `/admin/llm-providers` — `FallbackModel` rotates to next provider on failure.

## License

Hazlo is source-available software licensed under the
**Hazlo Source-Available Ethical License 1.0 (HSEL-1.0)**.

- **[LICENSE](LICENSE)** — Full license text. Permits personal, educational, research, and internal business use. Prohibits offering as a commercial service without permission.
- **[ETHICAL-USE.md](ETHICAL-USE.md)** — Ethical use restrictions: prohibits use for military purposes, weapons, mass surveillance, repression, and human rights violations. These restrictions are perpetual.

For questions about licensing or alternative arrangements, contact the licensor.

---

<p align="center">
  Built with care for communities and their events.
</p>
