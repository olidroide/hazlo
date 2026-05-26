---
name: tech-committee
description: Multi-perspective technical analysis. Evaluate decisions, architecture, and code through distinct expert roles before converging on a recommendation.
---

# Tech Committee Skill

Multi-perspective technical analysis. Evaluate decisions, architecture, and code through distinct expert roles before converging on a recommendation.

> ⚠️ **MODEL REQUIREMENT**: Use `opencode-go/qwen3.6-plus` (recommended). Kimi K2.6 **fails** — no JSON Schema support for MCP tools. If using weaker model, warn: "Switch to Qwen 3.6 Plus (press M) for better multi-perspective analysis."

## When to Use

- User says "committee", "tech committee", "review as committee", or invokes `/committee`
- User asks for multi-perspective analysis of a decision, design, or tradeoff
- User asks "what would different experts think about this?"
- Before major architectural decisions, database schema changes, or Python design choices

## Roles

The committee has 5 predefined perspectives. Use ALL of them unless the user specifies a subset:

| Role | Focus | Key Concerns |
|------|-------|---------------|
| **CTO** | Business value, risk, timeline, maintainability | "Does this move the needle? Can we sustain it? What breaks at 10x scale?" |
| **DB Architect** | Data model, queries, migrations, integrity | "Does this schema normalize well? Are migrations safe? What about indexes, constraints, N+1?" |
| **Python Lead** | Idiomatic code, performance, ecosystem, typing | "Is this Pythonic? Does it follow community conventions? Any gotchas with async/GIL/typing?" |
| **Security Engineer** | Attack surface, auth, secrets, input validation | "What can go wrong? Who can abuse this? Are we leaking data or exposing endpoints?" |
| **DevOps Lead** | Deployment, observability, rollback, infrastructure | "How does this deploy? Can we roll back? What alerts do we need? Where does it fail?" |

User can also define custom roles: `/committee roles=ML-Engineer,Product-Owner` — add them to the analysis.

## Output Format

ALWAYS output in this exact order with these exact section headers:

### 1. Analysis by Role

For each role, 3-5 bullet points. Concise, technical, opinionated. No hedging.

```
**[Role]**: [1-sentence stance]
- [Specific concern or observation]
- [Specific concern or observation]
- [Specific concern or observation]
```

### 2. Risks

Numbered list of risks ranked by likelihood × impact. Each risk states which role(s) flagged it.

```
1. **[Risk]** — [likelihood] — [impact] — flagged by: [roles]
2. ...
```

### 3. Disagreements

Where roles disagree. If no disagreements, state "No disagreements — consensus reached."

```
**[Role A]** says X. **[Role B]** says Y.
- Tension: [why they disagree]
- Resolution: [which position is stronger and why]
```

### 4. Convergent Proposal

A single, actionable proposal synthesizing the best from each role. This is the committee's recommendation. Must be concrete — no "it depends."

```
[Clear, specific proposal with enough detail to implement]
```

### 5. Final Recommendation

One paragraph. Direct. Actionable. If the committee needs more information, state exactly what's missing.

```
[Do X. Here's why. Here's the one thing to watch.]
```

## Rules

- Each role must have a DISTINCT opinion. No "I agree with the previous speaker."
- Risks must be specific to the context, not generic platitudes.
- Disagreements are valuable — don't smooth them over.
- The convergent proposal must resolve all disagreements explicitly.
- If the topic is trivial, responses should be proportionally brief. Don't over-engineer the analysis.
- Use caveman mode language rules (terse, technical, no filler).
- Always end with the final recommendation — it's the only section that must be actionable alone.

## Recommended Model

Use `opencode-go/kimi-k2.6` — best available model for multi-perspective role differentiation. Falls back to `opencode-go/qwen3.6-plus`.

Switch: `M opencode-go/kimi-k2.6` in OpenCode.

## Customization

User can customize via invocation:

- `/committee` — all 5 roles, standard format
- `/committee focus=DB` — emphasize DB Architect role, others brief
- `/committee roles=CTO,Security` — only these roles
- `/committee quick` — abbreviated format, max 2 bullets per role, skip disagreements if consensus
