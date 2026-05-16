# Hazlo

Smart event agenda with human review and source administration panel.

> Discover, normalize, and review events from multiple sources before showing them to your users.

---

## Table of Contents

- [Vision](#vision)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Event Data Model](#event-data-model)
- [Source Administration Panel](#source-administration-panel)
- [Human Review Flow](#human-review-flow)
- [Getting Started](#getting-started)
- [Running with Docker Compose](#running-with-docker-compose)
- [Developer Workflow](#developer-workflow)
- [Testing](#testing)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Vision

hazlo is an event agenda designed for modern cities, focused on data quality and
human editorial control. Its goal is to aggregate events from multiple sources,
normalize and enrich them, and let a person review each event before it becomes
visible to the public.

---

## Key Features

- Data ingestion from multiple configurable sources (websites, APIs, feeds, etc.).
- Source administration panel to:
  - Add new sources.
  - Verify their parsing.
  - Configure extraction frequency.
  - View last status (success/error) and extraction history.
  - Trigger manual extractions on demand.
- Event normalization to a common model, ready to be searched and filtered.
- Human-in-the-loop review flow to approve/edit events before publishing.
- Event classification:
  - Children's activities.
  - Events suitable for toddlers.
- Traceability focus:
  - Record of when and from where each event was extracted.
  - Information on what changes were made during manual review.
- Scheduled ingestion via Prefect (every 30 minutes by default).

---

## Architecture

hazlo follows **DDD & Clean Architecture** principles, clearly separating layers:

- **Domain**
  - Entities and Value Objects for events, sources, and reviews.
  - Pure business logic (no framework dependencies).
- **Application**
  - Use cases (application services) such as:
    - `IngestSource`
    - `ReviewEvent`
  - Flow orchestration (ingestion → normalization → review → publishing).
- **Infrastructure**
  - Repositories (async SQLAlchemy against PostgreSQL).
  - Source adapters (scrapers, HTTP clients, etc.).
  - HTTP API (FastAPI) and web layer (HTMX + Jinja2).
  - Prefect for scheduled task execution.

This separation allows evolving the domain model and data sources without
breaking the public interface.

---

## Tech Stack

- **Backend**
  - Python 3.12+
  - FastAPI (HTTP API and server-side views)
  - Pydantic v2 (input/output models and configuration)
  - SQLAlchemy 2.x async + PostgreSQL
- **Frontend**
  - HTMX (progressive interactions, HATEOAS)
  - Jinja2 (templates)
  - Tailwind CSS (utility styles)
- **Task scheduling**
  - Prefect 3.x (flows, deployments, worker)
- **Static typing & code quality**
  - ty (static type checker, strict mode)
  - Ruff (linter and formatter)
- **Packaging, env & tooling**
  - uv (package & project manager, environments, lockfile)
  - mise (dev tool / env manager and task runner)
- **Testing**
  - pytest
  - Factory Boy
  - Testcontainers (PostgreSQL and other external services in Docker)
- **Infrastructure**
  - Docker / Docker Compose for Prefect server, worker, and PostgreSQL.

---

## Event Data Model

Each event exposed by hazlo is normalized to a common model that includes at minimum:

- **Title**: event name.
- **Event location**
  - Full address.
  - Neighborhood.
  - Nearest metro stop (or other relevant transit).
- **Dates and times**
  - Start time.
  - End time.
- **Price**
  - Amount (if applicable).
  - Free entry or discount information.
- **Ticket sales**
  - URL or point of sale (required if tickets are sold).
  - Additional notes (e.g. "limited tickets", "box office only").
- **Classification**
  - Children's activity flag.
  - Toddler-friendly flag.
- **Metadata**
  - Original source (URL, external identifier).
  - Extraction date.
  - Status in the flow (pending review, approved, rejected, published).

---

## Source Administration Panel

The source administration panel is designed to give the content manager full
control over where data comes from and how it is processed:

- Source list:
  - Source name.
  - Type (web scraping, API, CSV, etc.).
  - Current status (active/inactive/running).
  - Last run and result (success/error).
  - "Ejecutar ahora" button for on-demand extraction.
- Source detail:
  - Parsing configuration.
  - Extraction frequency.
  - Preview of raw data and normalized result.
- Extraction history:
  - When each extraction was run.
  - Number of new/updated events.
  - Parsing errors with debug messages.

---

## Human Review Flow

Each event goes through a human-in-the-loop flow before becoming visible in the
public agenda:

1. **Ingestion**
   The system extracts data from configured sources and creates/updates events
   in "pending review" status. Runs every 30 minutes via Prefect, or manually
   from the admin panel.
2. **Review**
   A reviewer:
   - Verifies title, location, dates, price, and ticket link.
   - Completes or corrects information.
   - Marks whether it is a children's activity or toddler-friendly.
   - Approves or rejects the event.
3. **Publishing**
   Once approved, the event moves to "published" status and appears in the agenda.
4. **Audit**
   Records who reviewed the event, what changes were made, and when.
   Accessible via "Ver historial" on each event card.

This flow allows automating ingestion while maintaining editorial control and
data quality.

---

## Getting Started

> Assumes a local development environment with PostgreSQL available.
> Python and tools are managed by `mise` and `uv`.

### Quick start (app only, external DB)

1. **Install mise and uv (once per machine)**

   ```bash
   curl https://mise.run | sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**

   ```bash
   git clone https://github.com/<your-username>/hazlo.git
   cd hazlo
   mise install
   uv venv && source .venv/bin/activate
   uv sync
   ```

3. **Configure `.env`**

   ```env
   DATABASE_URL=postgresql+asyncpg://hazlo:hazlo@localhost:5433/hazlo
   HAZLO_ENV=development
   ```

4. **Run PostgreSQL** (if not already running)

   ```bash
   docker run -d --name hazlo-postgres \
     -e POSTGRES_USER=hazlo -e POSTGRES_PASSWORD=hazlo -e POSTGRES_DB=hazlo \
     -p 5433:5432 postgres:16-alpine
   ```

5. **Migrate and start**

   ```bash
   mise run migrate
   mise run dev
   ```

6. **Verify**

   - Admin panel: http://127.0.0.1:8000/admin/sources
   - Event review: http://127.0.0.1:8000/admin/events?status=pending

---

## Running with Docker Compose

For the full stack including Prefect server and worker:

```bash
# Start all infrastructure services (Postgres, Prefect server, worker, Redis)
docker compose up -d

# Wait for services to be healthy (Prefect takes ~60s to start)
docker compose ps

# Run migrations against the app database
# (use your local .env pointing to the Docker Postgres or a separate one)
mise run migrate

# Start the FastAPI app
mise run dev
```

### Prefect UI

Once running, access the Prefect dashboard at:
- http://localhost:4200

### Deploy flows

```bash
mise run deploy-flows
```

This registers:
- `ingest-all-sources` — runs every 30 minutes
- `ingest-single-source` — triggered manually or via API

### Prefect tasks

```bash
mise run prefect-server   # Start Prefect server locally
mise run prefect-worker   # Start a worker for the default pool
mise run deploy-flows     # Deploy flows to Prefect
```

---

## Developer Workflow

Common local commands using `mise` tasks:

| Task | Command | Description |
|------|---------|-------------|
| `dev` | `mise run dev` | Start FastAPI in dev mode |
| `test` | `mise run test` | Run pytest |
| `lint` | `mise run lint` | Run Ruff linter |
| `fmt` | `mise run fmt` | Run Ruff formatter |
| `typecheck` | `mise run typecheck` | Run ty type checker |
| `migrate` | `mise run migrate` | Apply Alembic migrations |
| `prefect-server` | `mise run prefect-server` | Start Prefect server |
| `prefect-worker` | `mise run prefect-worker` | Start Prefect worker |
| `deploy-flows` | `mise run deploy-flows` | Deploy Prefect flows |

---

## Testing

Run the test suite:

```bash
mise run test
```

Recommended practices:

- **Domain tests**: use case coverage for event creation, review, and ingestion;
  business rules (e.g. date validation, required ticket link for paid events).
- **Infrastructure tests**: repositories against PostgreSQL via Testcontainers;
  source adapters with mocked external responses.
- **Integration tests**: full ingestion → review → publishing flows.

---

## Roadmap

Some possible directions for hazlo:

- [ ] Advanced agenda filtering by neighborhood, event type, price range, and
      family-friendliness.
- [ ] Notifications (email / push) when relevant new events are added.
- [ ] Role system (source admin, event reviewer, read-only).
- [ ] Public API to expose events to third parties.
- [ ] Metrics and reports on event volume and quality per source.

---

## Contributing

Contributions are welcome. Guidelines:

- Open an issue clearly describing the improvement or bug.
- Add tests covering the new functionality or the fixed issue.
- Respect the layered architecture (Domain / Application / Infrastructure).
- Follow the project's style guides (formatting, strict typing, etc.).

---

## License

Hazlo is source-available software (not open source in the OSI sense), licensed
under the **Hazlo Source-Available Ethical License 1.0 (HSEL-1.0)**.

The code is visible for inspection, learning, private use, internal business
use, and contribution.

**License terms:**
- **LICENSE**: HSEL-1.0 — permits personal, educational, research, and internal
  business use. Prohibits offering as a commercial service without permission.
- **ETHICAL-USE.md**: human-readable summary of the ethical restrictions —
  prohibits use for military purposes, weapons, mass surveillance, repression,
  and human rights violations. These restrictions are perpetual.

For questions about licensing or alternative arrangements, contact the licensor.
