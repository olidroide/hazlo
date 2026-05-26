# Hazlo — Agent Instructions

> **Full documentation**: [docs/](../docs/) — especially [docs/ai-context.md](../docs/ai-context.md)
> for a dense AI-oriented knowledge base covering architecture, data model, conventions,
> and project decisions.

## Project Overview
Smart event agenda with human review and source administration panel.
Stack: Python 3.13+, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, HTMX, Jinja2, Tailwind CSS.

## Architecture (MANDATORY)
Follow DDD & Clean Architecture strictly:
- `hazlo/domain/` — Entities, Value Objects. Zero framework imports.
- `hazlo/application/` — Use Cases only. No SQLAlchemy, no FastAPI here.
- `hazlo/infrastructure/` — Repositories, API routes, adapters.

## Code Rules
- Python 3.13+ only. Always use `match/case`, `async/await`, strict type hints.
- Pydantic v2 for all input/output models. Use `model_config = ConfigDict(strict=True)`.
- SQLAlchemy 2.0 style: `select()`, `async with session:`, no legacy Query API.
- Ruff for formatting. `ty` for type checking (strict mode).
- `uv` for dependency management. Never use `pip` directly.

## Testing (TDD) — MANDATORY
- Write the test BEFORE the implementation.
- Use pytest + Factory Boy + Testcontainers for DB tests.
- Domain tests: pure unit tests, no DB needed.
- Infrastructure tests: use Testcontainers PostgreSQL.
- **Pre-commit hook enforces this:** commits with `hazlo/` changes but no `tests/` changes are blocked.
- Emergency bypass: `git commit --no-verify` (requires justification in commit message).

## CI — MANDATORY after every code change

After ANY code modification (write, edit, create, delete):

```bash
mise run ci
```

Runs: `fmt` → `lint` → `typecheck` → `test` (unit tests).

- Fix ALL errors before considering the task done.
- This is NOT optional. No commit without green CI.

## Commands
```bash
mise run ci        # fmt + lint + typecheck + test (MANDATORY post-change)
mise run dev        # fastapi dev
mise run test       # pytest
mise run lint       # ruff check
mise run typecheck  # ty check
```

## Versioning
- Timestamp format: `YYYYMMDDHHMM` (e.g., `202505191200`). NOT semver.
- Dev: `__version__ = "0.0.0"` in `hazlo/__init__.py` — don't modify during development.
- Release: automatic on merge to `main`. CI bumps, commits, tags, creates GitHub Release.
- Manual: `mise run release` (prefer CI).
- Check: `mise run version`.

## Branching
- `dev` — daily development, all PRs target this branch.
- `main` — releases only. Merge `dev` → `main` triggers auto-release.

## Language Policy
- Code (Python, tests, variable names, function names, params, log messages, error messages) → **English**
- Documentation (docs/, README, CHANGELOG, CONTRIBUTING) → **English**
- UI templates (Jinja2 HTML) stay Spanish (user-facing for Spanish-speaking users)

## NEVER
- No comments explaining obvious code.
- No `print()` for debugging — use `logging`.
- No `import *`.
- No direct writes to main/master — work in feature branches.
- Do NOT push to remote. Local commits only.
- No hardcoded credentials, tokens, or API keys — use `settings.py` + `.env`.
- No `eval()`, `exec()`, `pickle`, or `subprocess` with untrusted input.
- No disabling Ruff security rules (S-prefixed) without justification.

## Documentation (MANDATORY)
Documentation is not optional. This is an open-source project — docs are the first impression.

**Rule: every code change that affects behavior MUST update documentation.**

Before finishing any task, verify:
1. **`docs/ai-context.md`** — if you changed entities, routes, conventions, tooling, or architecture, update it
2. **`README.md`** — if you changed setup steps, tech stack, or features visible to new users, update it
3. **`CHANGELOG.md`** — if you added, changed, or removed a feature, add an entry under `[Unreleased]`
4. **`CONTRIBUTING.md`** — if you changed dev workflow, conventions, or versioning rules, update it

When in doubt, update. Stale docs are worse than no docs.

## LLM Layer — Pydantic AI + Gemini + OpenRouter

**Current implementation (pydantic-ai 1.102.0, Phase 3 complete — legacy removed):**
- `domain/llm_output.py` — Pydantic models for structured LLM output (`ClassificationOutput`, `LocationEnrichmentOutput`, `ClassificationResult`)
- `infrastructure/llm/agents/quality_classifier.py` — `QualityClassifierAgent` (pydantic-ai Agent with `output_type=ClassificationOutput`)
- `infrastructure/llm/agents/location_enrichment.py` — `LocationEnrichmentAgent` (pydantic-ai Agent with `output_type=LocationEnrichmentOutput`)
- `infrastructure/llm/prompts.py` — System prompts (`QUALITY_CLASSIFIER_V1`, `LOCATION_ENRICHMENT_V1`)
- `application/services/review_engine.py` — auto-approves events above confidence threshold

**Removed (Phase 3):**
- `GeminiProvider`, `OpenRouterProvider`, `LLMProvider` ABC — replaced by pydantic-ai `GoogleProvider`/`OpenRouterProvider`
- `LLMClient` — replaced by pydantic-ai `FallbackModel`
- `QualityClassifier`, `LLMEnrichmentService` — replaced by `QualityClassifierAgent`, `LocationEnrichmentAgent`

**Provider config** (admin UI at `/admin/llm-providers`):
- API keys encrypted at rest via Fernet (`infrastructure/crypto.py`) using `HAZLO_SECRET_KEY`
- Providers stored in DB, configured via admin panel (not in `.env`)
- `_build_llm_infrastructure()` in `flows.py` creates pydantic-ai `GoogleModel`/`OpenRouterModel` + `FallbackModel`
- Admin routes use pydantic-ai providers directly for `test_connection` and `list_models`

**Pydantic AI agents (Phase 3 — all legacy removed):**
- `QualityClassifierAgent` uses `Agent(model, output_type=ClassificationOutput, instructions=QUALITY_CLASSIFIER_V1)`
- `LocationEnrichmentAgent` uses `Agent(model, output_type=LocationEnrichmentOutput, instructions=LOCATION_ENRICHMENT_V1)`
- Structured output validated automatically by pydantic-ai — no manual JSON parsing
- Automatic retries on invalid output (configurable `retries` param, default 3)
- Exception handling: catches all exceptions and returns fallback results (confidence=0.0 for classifier, original event for enrichment)
- `FallbackModel` handles provider failover (Gemini → OpenRouter)
- `IngestSource` uses `QualityClassifierProtocol` and `LocationEnrichmentProtocol` (duck typing)
- All production call sites (`flows.py`, `ingest_source.py`) use new agents
- Tests use `FunctionModel` to mock structured output responses

**Circuit breaker (domain only):**
- `domain/circuit_breaker.py` — CLOSED→OPEN→HALF_OPEN state machine (kept for future use)
- Note: FallbackModel in pydantic-ai handles failover

**Rules:**
- Never store API keys in settings.py — use the DB with encrypted storage
- Gemini key sent via header `x-goog-api-key`, not query param
- `test_connection()` uses pydantic-ai Agent to verify connection
- New LLM services should use pydantic-ai Agents

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

## Testing Strategy — Mocks vs Testcontainers

**When to use mocks:**
- Unit tests for pure business logic (domain layer)
- API route tests that don't touch real DB
- LLM provider tests (mock HTTP responses)

**When to use Testcontainers:**
- Repository tests (real PostgreSQL, real SQL)
- Integration tests (full ingestion → review → publish flows)
- Any test that exercises SQLAlchemy queries/merges

**Critical lesson:** API tests with mocked repositories won't catch `session.add()` vs `session.merge()` bugs. Always add Testcontainers integration tests for repository methods.

## Prefect Deployment — Entrypoint Bug

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

## Performance Notes — LLM Classification

**Cost/time tradeoff:**
- 1063 events × ~2s per LLM call = ~30 minutes total
- Without LLM classification = ~7 seconds
- Consider batch processing or skipping LLM for low-priority sources

**Gemini quirks:**
- `QUALITY_CLASSIFIER_V1` prompt sometimes returns non-JSON
- `QualityClassifier._parse_response()` handles gracefully with defaults
- Monitor LLM response format and adjust prompts as needed

## Lessons Learned — Critical Gotchas

1. **Docker build requires README.md** — hatchling includes it in package metadata. `.dockerignore` must have `!README.md` to un-exclude it.

2. **DATABASE_URL in Docker** — `${DATABASE_URL:-...}` picks up host `.env` value. Use explicit `postgres:5432` for Docker internal, or shared `POSTGRES_*` vars.

3. **session.merge() is async** — requires `await self._session.merge()`, not `self._session.merge()`.

4. **Prefect entrypoint corruption** — `from_source().deploy()` corrupts module paths. Use `client.create_deployment()` directly.

5. **API tests use mocks** — won't catch repository bugs. Need Testcontainers integration tests for `save()` methods.

6. **LLM classification performance** — 1000+ events with LLM = 30 min. Consider batching or selective classification.

7. **Pre-commit hook enforces TDD** — commits with `hazlo/` changes but no `tests/` changes are blocked. Emergency bypass: `git commit --no-verify`.
