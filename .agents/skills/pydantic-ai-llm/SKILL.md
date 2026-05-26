# Pydantic AI — LLM Layer Skill

## Scope

Use Pydantic AI **only** for the single LLM call in the pipeline: `QualityClassifier`.
Do NOT use for parser, enrichment, dedup, review engine, admin panel, or any deterministic logic.

## Two Concepts: Coding Skills vs Runtime Capabilities

Pydantic AI has two separate concepts that are easy to conflate:

| Concept | What it is | Who uses it |
|---|---|---|
| **Coding Agent Skills** | SKILL.md files that help AI coding assistants generate correct Pydantic AI code | You (when writing code with Claude Code, Copilot, etc.) |
| **Runtime Capabilities** | `Capability` objects attached to `Agent` for reusable behavior (tools, hooks, settings) | The agent at runtime |

### Coding Agent Skills (for development)

The official skill is at **`pydantic/skills`** (https://github.com/pydantic/skills) — 61 stars, MIT license.

**Two installation paths:**

1. **Claude Code plugin marketplace:**
   ```
   claude plugin marketplace add pydantic/skills
   claude plugin install ai@pydantic-skills
   ```

2. **Cross-agent via `skills/` directory** (agentskills.io standard — compatible with Codex, Cursor, Gemini CLI, Claude Code):
   - `skills/building-pydantic-ai-agents` — tools, capabilities, structured output, streaming, testing, multi-agent
   - `skills/logfire-instrumentation` — observability for Python/JS/Rust

**Skill version:** `building-pydantic-ai-agents` v1.1.0

**Task routing (load only what you need):**

| I want to... | Load reference |
|---|---|
| Create/configure agents, output types, deps, run methods | `references/AGENTS-CORE.md` |
| Bundle reusable behavior, intercept lifecycle | `references/CAPABILITIES-AND-HOOKS.md` |
| Add function tools, toolsets, MCP | `references/TOOLS-CORE.md` |
| Provider-native web search, web fetch, code execution | `references/NATIVE-TOOLS.md` |
| Approval, retries, validators, timeouts, tool search | `references/TOOLS-ADVANCED.md` |
| Multimodal input, message history, context trimming | `references/INPUT-AND-HISTORY.md` |
| Test or debug agent behavior | `references/TESTING-AND-DEBUGGING.md` |
| Multi-agent patterns, graphs, durable execution, evals | `references/ORCHESTRATION-AND-INTEGRATIONS.md` |
| Compare abstractions, decision trees | `references/ARCHITECTURE.md` |

**Key gotchas (from official skill):**
- `@agent.tool` requires `RunContext` as first param; `@agent.tool_plain` must NOT have it
- Model strings need provider prefix: `'openai:gpt-5.2'` not `'gpt-5.2'`
- `TestModel` requires `agent.override()` — never set `agent.model` directly
- `str` in `output_type` allows plain text to end the run — omit to force structured output
- `history_processors` is deprecated — use `capabilities=[ProcessHistory(p), ...]`

**For Hazlo:** When migrating to Pydantic AI, load `building-pydantic-ai-agents` so the coding agent generates correct patterns. Most relevant sub-references: `AGENTS-CORE.md`, `CAPABILITIES-AND-HOOKS.md`, `TESTING-AND-DEBUGGING.md`.

### Runtime Capabilities (for the agent)

Pydantic AI capabilities are composable bundles of tools, hooks, instructions, and model settings.

**Top 5 capabilities for Hazlo** (in adoption order):

| Priority | Capability | Why |
|---|---|---|
| 1 | `Hooks` | Audit logging for every LLM call — required for human reviewability |
| 2 | `Instrumentation` | Tracing + cost tracking via Logfire or OTel — observability |
| 3 | `IncludeToolReturnSchemas` | Better Gemini compatibility — schemas in tool returns improve structured output |
| 4 | `pydantic-ai-shields` | Budget guard, PII detection, prompt injection protection — security for ingestion |
| 5 | `ThreadExecutor` | If running sync functions inside FastAPI — prevents blocking the event loop |

**NOT needed for Hazlo:**
- `Thinking` — no reasoning chain needed for classification
- `WebSearch` / `WebFetch` — classification uses event data, not web lookup
- `MCP` — no external tools needed
- `ToolSearch` — single tool, no search needed
- `subagents-pydantic-ai` — overkill for single-call pipeline
- `summarization-pydantic-ai` — no long context to compress

## Architecture Decision

```
application/
  └── ports/
        └── quality_classifier.py    # Protocol (port)

infrastructure/
  └── llm/
        ├── classifiers/
        │   ├── __init__.py
        │   ├── direct_gemini.py     # Current: httpx + manual JSON parse
        │   └── pydantic_ai.py       # Future: Agent[None, ClassificationResult]
        └── ...
```

**Rule:** Domain and use cases import from `application/ports/`, never from `infrastructure/llm/classifiers/`.

## Why Pydantic AI (partial adoption)

### Solves real problems

| Problem | Current code | Pydantic AI |
|---|---|---|
| Structured output + validation | Manual `json.loads()` + try/except | `output_type=ClassificationResult`, auto-retry on validation fail |
| Provider fallback | Hand-rolled loop in `LLMClient` | `FallbackModel(gemini, openrouter)` — built-in |
| Testing without LLM | Mock `LLMClient` manually | `TestModel()` or `FunctionModel` — auto-generates valid structured output |
| Accidental real LLM calls in tests | No safety net | `models.ALLOW_MODEL_REQUESTS = False` — global block |
| Token/cost tracking | Manual in `LLMCallRecord` | `result.usage` — automatic `input_tokens`, `output_tokens` |
| Gold dataset evaluation | Planned, not built | `pydantic_evals` — built-in eval framework with precision/recall |

### Does NOT solve (our responsibility)

- LLM provider CRUD in admin panel → our `LLMProviderModel` + routes
- API key encryption → our `crypto.py` (Fernet)
- Audit trail → our `llm_calls` table design
- Publication policy → our state machine + review engine
- Threshold configuration → our admin panel settings

## Implementation Pattern

### Port (application layer)

```python
# hazlo/application/ports/quality_classifier.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from hazlo.domain.event import Event


@dataclass(frozen=True)
class ClassificationResult:
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float


class QualityClassifierPort(Protocol):
    async def classify(self, event: Event) -> ClassificationResult: ...
```

### Direct Gemini implementation (current — keep as fallback)

```python
# hazlo/infrastructure/llm/classifiers/direct_gemini.py
# Current implementation: httpx + manual JSON parse
# Keep working, no changes needed
```

### Pydantic AI implementation (future — adopt when provider code grows)

```python
# hazlo/infrastructure/llm/classifiers/pydantic_ai.py
from __future__ import annotations

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterProvider, OpenRouterModel

from hazlo.application.ports.quality_classifier import ClassificationResult, QualityClassifierPort
from hazlo.domain.event import Event


class _ClassificationOutput(BaseModel):
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float


class PydanticAIQualityClassifier(QualityClassifierPort):
    def __init__(
        self,
        gemini_api_key: str,
        openrouter_api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
    ) -> None:
        gemini = GoogleModel(f"google:{model_name}", api_key=gemini_api_key)

        if openrouter_api_key:
            openrouter = OpenRouterModel(
                "openrouter:google/gemini-2.0-flash",
                provider=OpenRouterProvider(api_key=openrouter_api_key),
            )
            model = FallbackModel(gemini, openrouter)
        else:
            model = gemini

        self._agent = Agent[None, _ClassificationOutput](
            model,
            output_type=_ClassificationOutput,
            instructions=QUALITY_CLASSIFIER_PROMPT,
        )

    async def classify(self, event: Event) -> ClassificationResult:
        prompt = _build_prompt(event)
        result = await self._agent.run(prompt)
        return ClassificationResult(
            is_children_activity=result.output.is_children_activity,
            is_toddler_friendly=result.output.is_toddler_friendly,
            confidence=result.output.confidence,
        )
```

### Testing with TestModel

```python
# tests/infrastructure/llm/test_pydantic_ai_classifier.py
import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from hazlo.infrastructure.llm.classifiers.pydantic_ai import PydanticAIQualityClassifier

models.ALLOW_MODEL_REQUESTS = False  # Safety net


@pytest.fixture
def classifier():
    cls = PydanticAIQualityClassifier(gemini_api_key="test-key")
    with cls._agent.override(model=TestModel()):
        yield cls


@pytest.mark.asyncio
async def test_classify_returns_structured_output(classifier):
    event = make_event(title="Taller infantil de pintura")
    result = await classifier.classify(event)
    assert isinstance(result.is_children_activity, bool)
    assert isinstance(result.confidence, float)
```

### Testing with FunctionModel (deterministic control)

```python
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai import ModelMessage, ModelResponse

def mock_classification(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    # Return deterministic structured output for testing
    return ModelResponse.from_structured_output(
        {"is_children_activity": True, "is_toddler_friendly": False, "confidence": 0.95}
    )

@pytest.fixture
def classifier_deterministic():
    cls = PydanticAIQualityClassifier(gemini_api_key="test-key")
    with cls._agent.override(model=FunctionModel(mock_classification)):
        yield cls
```

## Migration Strategy

### Phase 1 (current — keep)
- Direct Gemini via `httpx` in `infrastructure/llm/providers/gemini.py`
- Manual JSON parsing in `quality_classifier.py`
- Hand-rolled fallback in `LLMClient`

### Phase 2 (adopt Pydantic AI)
1. Create `application/ports/quality_classifier.py` protocol
2. Create `infrastructure/llm/classifiers/pydantic_ai.py` implementation
3. Write tests with `TestModel` + `FunctionModel`
4. Wire up in `infrastructure/prefect/flows.py` via dependency injection
5. Keep direct Gemini implementation as alternative
6. Switch by changing which implementation is injected

### Phase 3 (optional — pydantic_evals)
- Use `pydantic_evals` for gold dataset evaluation
- Track precision/recall metrics automatically
- Integrate with Logfire for observability

## Dependencies

```toml
# pyproject.toml — add when migrating
[project.optional-dependencies]
llm = ["pydantic-ai>=1.0.0"]
```

Install: `uv add pydantic-ai`

## Key Pydantic AI Features Used

| Feature | Purpose | Docs |
|---|---|---|
| `Agent[deps, output_type]` | Structured output with validation + auto-retry | `/docs/ai/core-concepts/agent/` |
| `FallbackModel` | Gemini → OpenRouter automatic fallback | `/docs/ai/models/overview/#fallback-model` |
| `TestModel` | Zero-LLM unit tests | `/docs/ai/guides/testing/` |
| `FunctionModel` | Deterministic mock for complex test scenarios | `/docs/ai/guides/testing/` |
| `models.ALLOW_MODEL_REQUESTS = False` | Prevent accidental real LLM calls in tests | `/docs/ai/api/models/base/` |
| `Agent.override()` | Swap model in tests without changing app code | `/docs/ai/api/pydantic-ai/agent/` |
| `result.usage` | Automatic token tracking | `/docs/ai/api/pydantic-ai/usage/` |
| `pydantic_evals` | Gold dataset evaluation framework | `/docs/ai/evals/` |
| `Hooks` capability | Audit logging for LLM calls | `/docs/ai/core-concepts/capabilities/` |
| `Instrumentation` capability | Tracing + cost monitoring | `/docs/ai/integrations/logfire/` |
| `pydantic-ai-shields` | Budget guard, PII detection, prompt injection protection | External package |

## Key Pydantic AI Features NOT Used

| Feature | Why not |
|---|---|
| Agent loop / multi-step | Single-call classification only |
| Function tools | No tool calling needed for classification |
| `Thinking` capability | No reasoning chain needed |
| `WebSearch` / `WebFetch` | Classification uses event data, not web lookup |
| MCP / A2A | Irrelevant for this project |
| Graph / durable execution | Overkill for single-step pipeline |
| Streaming | Batch classification, no streaming needed |
| `subagents-pydantic-ai` | Overkill for single-call pipeline |
| `summarization-pydantic-ai` | No long context to compress |

## Rules

1. **Pydantic AI stays in `infrastructure/`** — never imported in `domain/` or `application/` (except the port)
2. **Port first** — define `QualityClassifierPort` before any implementation
3. **Two implementations** — direct Gemini (current) + Pydantic AI (future)
4. **Tests use TestModel** — never mock the LLM manually when using Pydantic AI
5. **ALLOW_MODEL_REQUESTS = False** — always set in test conftest
6. **No agent framework creep** — if Pydantic AI starts complicating things, revert to direct implementation
7. **Capabilities over custom code** — use `Hooks` for audit logging, `Instrumentation` for tracing, don't roll your own
8. **Shields before production** — add `pydantic-ai-shields` for budget guard + PII detection before going live
9. **Load official skill** — when writing Pydantic AI code, load `pydantic/skills` for correct patterns
