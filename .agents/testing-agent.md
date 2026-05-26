# Testing Agent Policy

> **Role**: Proposer and reviewer of tests. NOT final quality authority.
> **Scope**: Generate tests, find corner cases, detect coverage gaps.
> **Boundary**: Does NOT replace architectural judgment, human review, or testing strategy.

## When to Use

- Propose unit and edge-case tests for `domain/` and `application/services/`
- Generate parametrized tests, error cases, and combinations humans might miss
- Audit existing modules for missing edge-case coverage
- Propose async/integration test templates for `infrastructure/` and FastAPI routes

## Rules (MANDATORY)

### Structure
- One behavior per test — no multi-assert sprawl
- Descriptive names: `test_<module>_<scenario>_<expected_outcome>`
- Parametrize when cases share structure, not when they test different contracts
- Mock ONLY external dependencies (HTTP, DB, filesystem, LLM)
- Never test internal implementation details — only observable contract

### Coverage Categories (always propose in this order)
1. **Happy path** — valid input, expected output
2. **Invalid input** — missing fields, wrong types, empty values
3. **Boundaries** — min/max values, threshold edges (0.95 confidence, empty strings)
4. **Exceptions** — what raises, what returns None, what logs
5. **Invariants** — what never changes (frozen dataclass, idempotent operations)
6. **Idempotency** — same input twice = same output, no side effects
7. **Known regressions** — bugs that happened before, now covered

### Anti-Patterns (NEVER)
- No excessive mocks — if you mock more than 2 layers, test is too coupled
- No opaque setups — test should be readable in 10 seconds
- No testing private methods (`_internal`) unless they're part of the observable contract
- No "creative" tests that test hypothetical scenarios not in the spec
- No tests that assert on implementation details (internal state, call order of private methods)

## Workflow

```
1. Define contract (what should happen)
2. Write case table (input → expected output/error)
3. Write parametrized tests
4. Run tests → verify green
5. Human reviews → accepts valuable tests, rejects noise
```

## Module-Specific Guidance

### `domain/`
- Pure unit tests, zero imports from infrastructure
- Test entity invariants, value object equality, state machine transitions
- Focus on `is_valid()`, `can_transition_to()`, `with_status()`

### `application/services/`
- Test deterministic transformations (enrichment, dedup, classification)
- No side effects, no DB, no HTTP
- Use Factory Boy for test data when entities are complex

### `application/use_cases/`
- Test orchestration: correct service call order, error propagation
- Mock services, verify use case coordinates them correctly

### `infrastructure/`
- Propose templates, human selects which to keep
- Adapters: mock HTTP, test XML/JSON parsing edge cases
- Repositories: use Testcontainers PostgreSQL
- Routes: use `app.dependency_overrides`, not `patch(Repository)`

## Quality Bar

A test is valuable if:
- It would catch a real bug
- It documents a contract
- It's readable without comments
- It doesn't break when refactoring internals

A test is noise if:
- It tests the same thing as another test with different inputs
- It asserts on internal state that could change
- It requires 20+ lines of setup to understand
- It mocks the thing it's supposed to test
