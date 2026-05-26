# Agentic Event Ingestion System

## Vision

Hazlo's competitive advantage is **autonomous curation with human oversight**. Traditional event aggregators use static pipelines and manual curation. Hazlo uses a deterministic pipeline with targeted LLM classification — humans review only what the system cannot confidently decide.

**Core principle:** Deterministic first. LLM only where rules fail.

## Architecture: Deterministic Pipeline + 1 LLM Hook

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCE INPUT                                 │
│              RSS/XML  │  Websites  │  Email (IMAP)                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. ADAPTER (deterministic)                                         │
│  Role: Fetch + parse source into raw event dicts                    │
│  Technique: XML parse (RSS), justhtml (Web), IMAP (Email)           │
│  LLM: NO                                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ list[dict]
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. IDEMPOTENCY CHECK (deterministic)                               │
│  Role: Skip events already ingested (exactly-once semantics)        │
│  Technique: SHA-256 key from source_url + title + start_at          │
│  LLM: NO                                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ unique events
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. ENRICHMENT SERVICE (deterministic)                              │
│  Role: Normalize dates, prices, addresses. Extract metro from       │
│        address using lookup table. Set category from source meta.   │
│  Technique: Regex, lookup tables, string normalization              │
│  LLM: NO                                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ enriched dict
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. DEDUP SERVICE (deterministic)                                   │
│  Role: Detect duplicate events across sources                       │
│  Technique: PostgreSQL pg_trgm similarity + date + venue match      │
│  LLM: NO                                                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ unique events
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. QUALITY CLASSIFIER (LLM — 1 call per event)                     │
│  Role: Classify is_children_activity, is_toddler_friendly,          │
│        assign confidence_score based on completeness + quality      │
│  Technique: LLM structured output (Pydantic)                        │
│  LLM: YES — configurable provider (Gemini default, free tier)       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ scored event
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. REVIEW ENGINE (rule-based)                                      │
│  Role: Decide approve/reject/flag based on rules + confidence       │
│                                                                      │
│  Rules:                                                              │
│  - Required fields present? (title, address, start_at)              │
│  - Ticket URL if paid event?                                        │
│  - confidence_score >= auto_approve_threshold?                      │
│                                                                      │
│  confidence >= threshold → auto-approve → APPROVED                  │
│  Missing required fields → flag → PENDING (human review)            │
│  confidence < threshold → flag → PENDING (human review)             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  DATABASE + HUMAN REVIEW QUEUE                                      │
│  Auto-approved → APPROVED (skip human queue)                        │
│  Flagged → PENDING (human reviews via admin panel)                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Not 5 Agents?

| Step | Original (5 agents) | MVP (deterministic + 1 LLM) | Why |
|---|---|---|---|
| Parser | Agent with auto-healing | Deterministic adapter | Regex/XML parse is reliable, no LLM needed |
| Enrichment | LLM classification | Lookup tables + regex | Metro/barrio from address = dictionary lookup |
| Dedup | Semantic embeddings | pg_trgm similarity | Trigram + date + venue = 95% accuracy, $0 cost |
| Quality | LLM | **LLM (1 call)** | This is where LLM adds real value |
| Review | LLM decision | Rule engine | Rules are deterministic, auditable, free |

**Result:** 1 LLM call per event instead of 3-5. Cost: ~$0/month with Gemini free tier.

## LLM Provider Management

### Key Feature: Admin Panel for LLM Providers

No vendor lock-in. Configure, test, and switch LLM providers from the admin panel without code changes or restarts.

### Provider Configuration

```
┌──────────────────────────────────────────────────────────────┐
│  LLM Providers                                    [+ Add]    │
├──────────────────────────────────────────────────────────────┤
│  Name              Model                      Status   Cost  │
│  ─────────────────────────────────────────────────────────── │
│  Gemini (default)  google/gemini-2.0-flash    Active   $0    │
│  OpenRouter        google/gemini-2.0-flash    Inactive $0.10 │
│  OpenAI            gpt-4o-mini                Inactive $0.15 │
│                                                              │
│  [Test Connection]  [Set Active]  [Edit]  [Delete]           │
└──────────────────────────────────────────────────────────────┘
```

Each provider stores:
- `name` — display name
- `provider_type` — `gemini` | `openrouter` | `openai` | `anthropic`
- `model` — model identifier
- `api_key` — encrypted (Fernet)
- `is_active` — only one active at a time
- `priority` — fallback order
- `max_calls_per_run` — rate limit
- `cost_per_1k_tokens` — for tracking

### Provider Switching Flow

1. Admin adds new provider in panel
2. Clicks "Test Connection" → sends test prompt, validates response
3. Sets as active → system uses new provider for next ingestion run
4. If provider fails → automatic fallback to previous active provider
5. All switches logged in audit trail

### Cost Strategy

| Provider | Model | Input ($/1M) | Output ($/1M) | Free Tier | Monthly Cost* |
|---|---|---|---|---|---|
| **Google Gemini** | **2.0 Flash** | **$0.10** | **$0.40** | **15 req/min** | **$0** |
| Google Gemini | 2.0 Flash Lite | $0.075 | $0.30 | 15 req/min | $0 |
| OpenRouter | google/gemini-2.0-flash | $0.10 | $0.40 | No | $1.20 |
| OpenRouter | meta-llama/llama-3.1-8b | $0.03 | $0.06 | No | $0.27 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | No | $1.80 |
| Anthropic | claude-3.5-haiku | $0.80 | $4.00 | No | $10.80 |

*Based on 3000 events/month, 2K input + 500 output tokens per event.

**Default:** Google Gemini 2.0 Flash via direct API → free tier covers all ingestion needs.

**Fallback:** Configure OpenRouter as secondary provider from admin panel.

### Configuration

```python
# settings.py
llm_provider: str = "gemini"  # gemini | openrouter | openai | anthropic
gemini_api_key: str = ""  # Google AI Studio API key
gemini_model: str = "gemini-2.0-flash"
llm_timeout: int = 30  # seconds
llm_max_retries: int = 2
auto_approve_threshold: float = 0.95  # configurable from admin
```

## Implementation Plan

### Phase 1: Quality Classifier + Review Engine + LLM Admin (MVP)

**Goal:** Auto-classify `is_children_activity`, `is_toddler_friendly`, assign `confidence_score`. Reduce human review by ~60%. Admin panel for LLM providers.

**New files:**
```
hazlo/application/
├── services/
│   ├── __init__.py
│   ├── enrichment_service.py    # Deterministic: normalize, lookup metro
│   ├── dedup_service.py         # Deterministic: pg_trgm similarity
│   ├── quality_classifier.py    # LLM: classification + confidence
│   └── review_engine.py         # Rules: approve/reject/flag

hazlo/infrastructure/
├── llm/
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py              # LLMProvider protocol
│   │   ├── gemini.py            # Google Gemini direct API
│   │   ├── openrouter.py        # OpenRouter gateway
│   │   └── openai.py            # OpenAI direct API
│   ├── client.py                # Provider router + fallback
│   └── prompts.py               # System prompts
├── crypto.py                    # Fernet encrypt/decrypt for API keys

hazlo/domain/
├── llm_provider.py              # LLMProvider entity
└── source_health.py             # SourceHealth entity
```

**Files to modify:**
- `domain/event.py` — add `confidence_score: float`, `agent_review: dict`
- `application/use_cases/ingest_source.py` — integrate pipeline
- `infrastructure/db/models.py` — new tables + columns
- `infrastructure/api/routes/` — LLM provider admin routes
- `settings.py` — LLM configuration
- `templates/admin/` — LLM provider management UI

**DB changes:**
```sql
-- New columns on events
ALTER TABLE events ADD COLUMN confidence_score FLOAT DEFAULT NULL;
ALTER TABLE events ADD COLUMN agent_review JSONB DEFAULT NULL;

-- extraction_runs table ALREADY EXISTS (migration 001_initial)
-- Phase 1 adds columns to it:
ALTER TABLE extraction_runs ADD COLUMN documents_fetched INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN events_extracted INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN events_created INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN events_flagged INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN events_auto_approved INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN events_auto_rejected INTEGER DEFAULT 0;
ALTER TABLE extraction_runs ADD COLUMN snapshot JSONB DEFAULT NULL;
```

### Phase 2: pg_trgm Dedup + Geocoding Enrichment

- PostgreSQL `pg_trgm` extension for trigram similarity
- Address → metro/barrio lookup table
- Category inference from source metadata + description keywords

### Phase 3: Auto-healing Parser (only if Phase 1-2 stable)

- Monitor adapter failure rate per source
- On threshold breach, trigger LLM to analyze HTML and suggest new selectors
- Human approves suggested selectors before applying

## Security

### API Key Encryption
- All LLM API keys encrypted with Fernet (symmetric)
- `HAZLO_SECRET_KEY` env var — never in code or DB
- Encrypt at save time in admin panel, decrypt at use time

### Prompt Security
- Sanitize HTML before sending to LLM (strip tags, escape)
- System prompt immutable — user content in separate message
- Structured output via Pydantic — reject malformed responses
- No PII in LLM calls (emails, phones stripped)

### Rate Limiting
- Batch events: 10 per LLM call
- Circuit breaker: 3 failures → fallback provider or rules-only
- Cost guard: max $5/month alert (configurable)

## Admin Panel Features

### LLM Provider Management
- Add/edit/delete providers
- Test connection button
- Set active provider
- View cost per provider
- Switch without restart

### Source Health Dashboard
- Failure rate per source
- Events per run average
- Average confidence score
- Last success/failure timestamps
- Quick actions: disable source, run now, view events

### Event Review Queue (enhanced)
- Confidence score badge on each card
- LLM reasoning tooltip
- Filter by confidence range
- Bulk approve above threshold
- Override agent decision

## Observability

### Metrics
- `pipeline.events_per_run` — events processed per ingestion
- `pipeline.auto_approve_rate` — % auto-approved
- `pipeline.avg_confidence` — average confidence score
- `llm.calls_per_month` — total LLM calls
- `llm.cost_per_month` — running cost total
- `llm.error_rate` — % failed LLM calls
- `source.failure_rate` — per-source failure rate

### Logging
- Every LLM call: provider, model, tokens, cost, latency, error
- Every provider switch: old → new, reason, timestamp
- Pipeline: total time, events processed, errors, auto-approved count

## Comparison with Existing Solutions

| Feature | Hazlo | Eventbrite | Facebook Events | Meetup |
|---|---|---|---|---|
| Auto-ingestion | Multi-source, adaptive | Manual | Platform-only | Platform-only |
| Classification | LLM + rules | Manual tags | Opaque algorithm | Manual |
| Deduplication | pg_trgm + date + venue | None | Platform-only | None |
| Quality scoring | Confidence-scored | None | Engagement-based | None |
| LLM provider switching | Admin panel, zero downtime | N/A | N/A | N/A |
| Human review | Configurable threshold | N/A | N/A | N/A |
| Cost per event | ~$0 (Gemini free tier) | Platform fee | Ad-driven | Subscription |
| Transparency | Full audit trail | Opaque | Opaque | Opaque |

## Engineering Standards

### Code Organization

```
hazlo/
├── domain/                    # Entities, value objects, enums, business rules
│   ├── event.py               # Event, EventStatus, Location, Price, TicketInfo
│   ├── source.py              # Source, SourceType, SourceStatus
│   ├── review.py              # Review, ReviewAction
│   ├── llm_provider.py        # LLMProvider entity
│   └── source_health.py       # SourceHealth entity
│
├── application/               # Use cases + services + ports
│   ├── use_cases/             # Orchestrate services, no framework imports
│   │   ├── ingest_source.py   # Main ingestion use case
│   │   └── review_event.py    # Human review use case
│   └── services/              # Deterministic + LLM services
│       ├── enrichment_service.py   # Normalize dates, prices, addresses
│       ├── dedup_service.py        # pg_trgm similarity check
│       ├── quality_classifier.py   # LLM classification
│       └── review_engine.py        # Rule-based decision
│
├── infrastructure/            # Implementations of ports
│   ├── adapters/              # Source connectors (RSS, Web, Email)
│   ├── api/                   # FastAPI routers + schemas + deps
│   ├── db/                    # SQLAlchemy models + repositories
│   ├── llm/                   # LLM provider implementations
│   │   ├── providers/
│   │   │   ├── base.py        # LLMProvider protocol
│   │   │   ├── gemini.py      # Google Gemini direct
│   │   │   └── openrouter.py  # OpenRouter gateway
│   │   ├── client.py          # Provider router + fallback
│   │   └── prompts.py         # System prompts
│   ├── crypto.py              # Fernet encrypt/decrypt
│   └── prefect/               # Orchestration flows
│
└── main.py                    # FastAPI app entry point
```

### Dependency Rules (STRICT)

| Layer | Can import from | Cannot import from |
|---|---|---|
| `domain/` | Nothing | `application/`, `infrastructure/` |
| `application/` | `domain/` | `infrastructure/` |
| `infrastructure/` | `domain/`, `application/` | — |
| `main.py` | `infrastructure/`, `application/` | — |

**Never:**
- Import FastAPI, SQLAlchemy, httpx, or any framework in `domain/`
- Put business logic in routers, templates, or Prefect flows
- Use `import *` or circular imports
- Hardcode API keys, URLs, or credentials

### Service Contract

Every service follows the same explicit pattern:

```python
# application/services/enrichment_service.py
class EnrichmentService:
    """Deterministic: normalize dates, prices, addresses."""

    async def execute(self, raw_event: dict) -> dict:
        """Input: raw event dict. Output: enriched event dict.

        No side effects. No DB access. No LLM calls.
        """
        ...
```

```python
# application/services/quality_classifier.py
class QualityClassifier:
    """LLM: classify event properties + confidence score."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    async def execute(self, event: Event) -> ClassificationResult:
        """Input: Event domain object. Output: ClassificationResult.

        Single LLM call. Structured output via Pydantic.
        """
        ...
```

### Testing Strategy

| Layer | Test type | Tools | Speed |
|---|---|---|---|
| `domain/` | Pure unit, sync | pytest | < 10ms |
| `application/services/` | Unit with mocks | pytest, unittest.mock | < 50ms |
| `application/use_cases/` | Integration with mocked repos | pytest, AsyncMock | < 100ms |
| `infrastructure/adapters/` | Unit with mocked HTTP | pytest, httpx mock | < 200ms |
| `infrastructure/db/` | Integration with real DB | testcontainers postgres | < 5s |
| `infrastructure/llm/` | Unit with mocked HTTP | pytest, httpx mock | < 200ms |
| `infrastructure/api/` | Integration with mocked deps | httpx ASGITransport | < 500ms |

**Rules:**
- Test BEFORE implementation (TDD)
- One test file per module: `tests/<layer>/test_<module>.py`
- Domain tests: synchronous, no I/O, no mocks needed
- Service tests: mock only external dependencies (LLM client, DB)
- Never mock domain entities
- CI runs: `mise run ci` (fmt + lint + typecheck + unit tests)

### Change Policy

1. **Small, reversible changes** — one PR per use case or service
2. **Test first** — write failing test, then implement
3. **No hidden side effects** — every function's inputs/outputs explicit
4. **No generic helpers** — if a helper is used once, inline it
5. **Audit every automatic decision** — LLM calls, auto-approvals, rejections all logged
6. **Human reviewable** — any automatic decision must be explainable with persisted inputs, rules, and outputs

### Human Reviewability

Every automatic decision in the pipeline must be traceable:

| Step | What's persisted | Where to find it |
|---|---|---|
| Adapter fetch | Raw response, parse errors | `source_health.last_failure_at`, logs |
| Enrichment | Normalized fields, lookup results | Event fields (address, metro, category) |
| Dedup | Similarity score, matched event ID | `agent_review.duplicate_of` |
| Quality classification | LLM prompt, response, confidence, model | `llm_calls` table, `events.confidence_score` |
| Review decision | Rules evaluated, threshold, action | `reviews` table, `events.agent_review` |

If a human cannot explain why an event was auto-approved or rejected by looking at these records, the pipeline has a bug.

## Publication Policy

**Absolute rule:** The machine can APPROVE but never PUBLISH. Only humans publish.

### State Machine

```
PENDING ──auto/review──▶ APPROVED ──human only──▶ PUBLISHED
   │
   └──────reject──────▶ REJECTED (terminal)
```

| Transition | Who | When |
|---|---|---|
| PENDING → APPROVED | Machine (confidence >= threshold) OR Human | Auto-approve or manual review |
| PENDING → REJECTED | Machine (confidence < threshold) OR Human | Auto-reject or manual review |
| APPROVED → PUBLISHED | **Human only** | Manual publish action in admin panel |
| APPROVED → REJECTED | **Human only** | Change of mind after auto-approve |

**Rationale:** Auto-approve reduces human workload. Auto-publish removes the safety net. PUBLISHED is the public-facing state — it must have a human signature.

### Configurable Threshold

The `auto_approve_threshold` (default 0.95) controls when the machine auto-approves vs flags for human review. This is adjustable from the admin panel without code changes.

| Threshold | Effect | Use case |
|---|---|---|
| 0.99 | Almost everything goes to human | New source, untested pipeline |
| 0.95 | Balanced (default) | Stable sources, proven classifier |
| 0.80 | Aggressive auto-approve | High-volume, low-risk events |
| 1.00 | No auto-approve | Audit mode, compliance |

## Extraction Runs

Every ingestion run is tracked as an `ExtractionRun` record. This is the operational backbone for source health, debugging, and audit.

### Entity (already exists in DB)

```python
# infrastructure/db/models.py — ExtractionRunModel
class ExtractionRunModel(Base):
    __tablename__ = "extraction_runs"

    id: UUID
    source_id: UUID          # which source
    started_at: datetime     # when run began
    finished_at: datetime | None  # when run ended
    status: str              # "running" | "success" | "error"
    events_found: int        # total raw events extracted
    errors: str | None       # error messages if any
```

### Fields to add (Phase 1)

| Field | Type | Purpose |
|---|---|---|
| `documents_fetched` | int | Raw documents/pages retrieved from source |
| `events_extracted` | int | Events parsed from raw documents |
| `events_created` | int | New events saved to DB (not duplicates) |
| `events_flagged` | int | Events sent to human review queue |
| `events_auto_approved` | int | Events auto-approved by classifier |
| `events_auto_rejected` | int | Events auto-rejected by classifier |
| `snapshot` | JSONB | Raw response sample for debugging |

### Lifecycle

```
Source triggers run → ExtractionRun(status="running", started_at=now)
    │
    ├── Adapter fetch → documents_fetched = N
    ├── Parse → events_extracted = M
    ├── Dedup → events_created = K
    ├── Quality classify → events_auto_approved, events_flagged, events_auto_rejected
    │
    └── Run complete → status="success"|"error", finished_at=now
```

### Admin Panel: Source Detail

The source detail page (`/admin/sources/{id}`) shows:
- Current status (active/inactive)
- Last run: timestamp, status, events found
- Extraction history table: date, status, events found, errors
- Quick actions: run now, toggle active, view events, edit config

## Source Onboarding UX

Complete journey for adding and operating a source from the admin panel.

### Step 1: Add Source

1. Click "Nueva fuente" on `/admin/sources`
2. Fill: name, type (RSS/Web/Email), URL (or IMAP config), fetch interval
3. Submit → source created, status=active

### Step 2: Test Connection

1. Click "Probar conexión" on source detail
2. System runs a single fetch (no save)
3. Shows: connection OK/failed, raw response preview, parse errors
4. If failed: shows error message, suggests fix

### Step 3: Preview Parse

1. Click "Vista previa" on source detail
2. System runs full pipeline (fetch + parse + enrich) without saving
3. Shows: 5 sample events with all fields populated
4. Highlights: missing required fields, low confidence scores
5. Human validates: "Looks good" or "Needs adjustment"

### Step 4: Configure Frequency

1. Set fetch interval (default: 60 min)
2. System schedules via Prefect deployment
3. Shows next scheduled run time

### Step 5: Monitor

After source is live, the detail page shows:
- **Health metrics**: failure rate, avg events/run, avg confidence
- **Last 10 runs**: date, status, events found, errors
- **Events from this source**: link to filtered event list
- **Quick actions**: run now, pause, edit, delete

### Source States

| State | Meaning | Actions available |
|---|---|---|
| `active` | Running on schedule | Pause, run now, edit, delete |
| `inactive` | Paused, no scheduled runs | Activate, edit, delete |
| `error` | Last run failed | View error, run now, edit, delete |
| `testing` | Connection test in progress | View test results |

## LLM Evaluation

Governance for the Quality Classifier. Without evaluation, the classifier is a black box.

### Gold Dataset

Maintain a labeled dataset of events with known classifications:

```
tests/data/gold_events.jsonl
{"title": "...", "description": "...", "is_children": true, "is_toddler": false, "expected_confidence": 0.92}
{"title": "...", "description": "...", "is_children": false, "is_toddler": false, "expected_confidence": 0.88}
```

Minimum: 50 events covering edge cases (ambiguous titles, multi-language, missing data).

### Metrics

| Metric | Target | How measured |
|---|---|---|
| Precision (is_children) | >= 0.90 | TP / (TP + FP) on gold dataset |
| Recall (is_children) | >= 0.85 | TP / (TP + FN) on gold dataset |
| Precision (is_toddler) | >= 0.85 | TP / (TP + FP) on gold dataset |
| Recall (is_toddler) | >= 0.80 | TP / (TP + FN) on gold dataset |
| Confidence calibration | >= 0.80 | Correlation between predicted confidence and actual accuracy |

### Prompt Versioning

Every prompt change is tracked:

```python
# infrastructure/llm/prompts.py
QUALITY_CLASSIFIER_V1 = """..."""
QUALITY_CLASSIFIER_V2 = """..."""

# Each run logs which prompt version was used
```

Prompt versions stored in `llm_calls.prompt_version` column.

### Evaluation Schedule

| Trigger | Action |
|---|---|
| Before deploying new prompt | Run gold dataset, compare metrics |
| After changing model/provider | Run gold dataset, compare metrics |
| Weekly (automated) | Run gold dataset, alert if metrics drop > 5% |
| Monthly (manual) | Review false positives/negatives, update gold dataset |

### Rollback Criteria

If metrics drop below target after a change:

1. Revert to previous prompt version
2. Revert to previous model/provider
3. Log the rollback reason in audit trail
4. Notify admin via email/log

### Admin Panel: Classifier Health

- Current model + prompt version in use
- Last evaluation: date, precision, recall, calibration
- Trend chart: precision/recall over time
- False positive/negative samples for review
- "Re-evaluate now" button

## Related Documents

- [Web Parsing Research](./web-parsing-research.md) — connector design research
- [AI Context](./ai-context.md) — development AI agent instructions
