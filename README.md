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
- Event normalization to a common model, ready to be searched and filtered.
- Human-in-the-loop review flow to approve/edit events before publishing.
- Event classification:
  - Children's activities.
  - Events suitable for toddlers.
- Traceability focus:
  - Record of when and from where each event was extracted.
  - Information on what changes were made during manual review.

---

## Architecture

hazlo follows **DDD & Clean Architecture** principles, clearly separating layers:

- **Domain**
  - Entities and Value Objects for events, sources, and reviews.
  - Pure business logic (no framework dependencies).
- **Application**
  - Use cases (application services) such as:
    - `CreateEventFromSource`
    - `ReviewEvent`
    - `ScheduleSourceFetch`
  - Flow orchestration (ingestion → normalization → review → publishing).
- **Infrastructure**
  - Repositories (async SQLAlchemy against PostgreSQL).
  - Source adapters (scrapers, HTTP clients, etc.).
  - HTTP API (FastAPI) and web layer (HTMX + Jinja2).
  - Task queue / scheduler integration (when applicable).

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
- **Other (optional / recommended)**
  - Docker / Docker Compose for development and deployment.
  - Task queue for periodic ingestion tasks (e.g., RQ, Celery, etc.).

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
  - Current status (active/inactive).
  - Last run and result (success/error).
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
   in "pending review" status.
2. **Review**
   A reviewer:
   - Verifies title, location, dates, price, and ticket link.
   - Completes or corrects information.
   - Marks whether it is a children's activity or toddler-friendly.
3. **Publishing**
   Once approved, the event moves to "published" status and appears in the agenda.
4. **Audit**
   Records who reviewed the event, what changes were made, and when.

This flow allows automating ingestion while maintaining editorial control and
data quality.

---

## Getting Started

> Assumes a local development environment with PostgreSQL available.
> Python and tools are managed by `mise` and `uv`.

1. **Install mise and uv (once per machine)**

   ```bash
   # mise — dev tool & env manager
   curl https://mise.run | sh

   # uv — Python package & project manager
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone the repository**

   ```bash
   git clone https://github.com/<your-username>/hazlo.git
   cd hazlo
   ```

3. **Activate project tools with mise**

   The `mise.toml` in the project root pins Python, `ruff`, `uv`, and other tools.

   ```bash
   mise install
   ```

4. **Create the virtual environment and install dependencies**

   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv sync
   ```

5. **Configure environment variables**

   Create a `.env` file with at least:

   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hazlo
   HAZLO_ENV=development
   ```

6. **Apply migrations / initialize the database**

   ```bash
   alembic upgrade head
   ```

7. **Start the application**

   ```bash
   uv run fastapi dev hazlo/main.py
   ```

8. **Verify everything works**

   - API / web: http://127.0.0.1:8000
   - Interactive docs (OpenAPI): http://127.0.0.1:8000/docs
   - Event review / source panel: e.g. `/admin/sources`, `/admin/events`

---

## Developer Workflow

Common local commands using `mise` tasks and `uv`:

- **Run the app in dev mode**

  ```bash
  mise run dev        # uv run fastapi dev hazlo/main.py
  ```

- **Run tests**

  ```bash
  mise run test       # uv run pytest
  ```

- **Type checking (ty)**

  ```bash
  mise run typecheck  # uv run ty check src
  ```

- **Lint & format (Ruff)**

  ```bash
  mise run lint       # uv run ruff check src
  mise run fmt        # uv run ruff format src
  ```

Exact commands depend on your `mise.toml`, which defines the task shortcuts.

---

## Testing

Run the test suite:

```bash
pytest
```

Recommended practices:

- **Domain tests**: use case coverage for event creation and updates; business
  rules (e.g. date validation, required ticket link for paid events).
- **Infrastructure tests**: repositories against PostgreSQL via Testcontainers;
  source adapters with mocked external responses.
- **Integration / end-to-end tests**: full ingestion → review → publishing flows.

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
