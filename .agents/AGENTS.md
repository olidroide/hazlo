# Hazlo — Agent Instructions

## Project Overview
Smart event agenda with human review and source administration panel.
Stack: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, HTMX, Jinja2, Tailwind CSS.

## Architecture (MANDATORY)
Follow DDD & Clean Architecture strictly:
- `hazlo/domain/` — Entities, Value Objects. Zero framework imports.
- `hazlo/application/` — Use Cases only. No SQLAlchemy, no FastAPI here.
- `hazlo/infrastructure/` — Repositories, API routes, adapters.

## Code Rules
- Python 3.12+ only. Always use `match/case`, `async/await`, strict type hints.
- Pydantic v2 for all input/output models. Use `model_config = ConfigDict(strict=True)`.
- SQLAlchemy 2.0 style: `select()`, `async with session:`, no legacy Query API.
- Ruff for formatting. `ty` for type checking (strict mode).
- `uv` for dependency management. Never use `pip` directly.

## Testing (TDD)
- Write the test BEFORE the implementation.
- Use pytest + Factory Boy + Testcontainers for DB tests.
- Domain tests: pure unit tests, no DB needed.
- Infrastructure tests: use Testcontainers PostgreSQL.

## Commands
```bash
mise run dev        # fastapi dev
mise run test       # pytest
mise run lint       # ruff check
mise run typecheck  # ty check
```

## NEVER
- No comments explaining obvious code.
- No `print()` for debugging — use `logging`.
- No `import *`.
- No direct writes to main/master — work in feature branches.
- Do NOT push to remote. Local commits only.
