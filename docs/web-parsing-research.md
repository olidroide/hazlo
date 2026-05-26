# Web Parsing Research

> Evaluation of tools and approaches for web parsing in Hazlo's Prefect-based ingestion pipeline.
> Last reviewed: 2026-05-20

---

## Current Stack: qcrawl + justhtml

**Decision:** Primary stack for all web source connectors.

| Layer | Tool | Purpose |
|-------|------|---------|
| Fetch | qcrawl | Async crawling, queues, middlewares, HTTP + headless |
| Parse | justhtml | Pure-Python HTML5 parser, tolerant of broken markup |

**Connector pattern:**
```
fetch (qcrawl) → raw HTML → parse (justhtml) → DTOs → map_to_domain → Event
```

**Source types:**
- `WEB_STATIC` — qcrawl HTTP downloader (no JS needed)
- `WEB_DYNAMIC` — qcrawl with headless browser (Playwright/Camoufox)
- `RSS/XML_FEED` — feed parser
- `EMAIL_NEWSLETTER` — IMAP/webhook → HTML body

**Resilience strategy:**
- Semantic selectors + key-text search + heuristics
- No fragile CSS-only selectors
- Log representative examples for future adjustments

**See skill:** `.agents/skills/scraping-qcrawl-justhtml/SKILL.md`

---

## Obscura Evaluation

**Repo:** https://github.com/h4ckf0r0day/obscura
**Stars:** 13.4k | **Lang:** Rust | **License:** Apache-2.0

### What it is

Headless browser engine in Rust. Drop-in replacement for headless Chrome.
Runs JS via V8, supports Chrome DevTools Protocol (CDP).
Compatible with Puppeteer and Playwright.

### Metrics vs Chrome

| Metric | Obscura | Headless Chrome |
|--------|---------|-----------------|
| Memory | 30 MB | 200+ MB |
| Binary size | 70 MB | 300+ MB |
| Anti-detect | Built-in (stealth mode) | None |
| Page load | 85 ms | ~500 ms |
| Startup | Instant | ~2 s |

### Key features

- CLI: `fetch`, `serve`, `scrape` commands
- Docker: multi-stage distroless image, ~57 MB
- CDP server: `ws://localhost:9222` — Puppeteer/Playwright compatible
- Stealth mode: anti-fingerprinting, tracker blocking (3520 domains)
- MCP server for AI agents
- Dump formats: html, text, links, markdown, original

### Fit assessment

| Aspect | Verdict |
|--------|---------|
| Fetch/crawl | ✅ Excellent for JS-heavy sites |
| Parsing | ❌ Not a parser — only renders HTML |
| Python integration | ⚠️ Via subprocess or CDP (Puppeteer/Playwright) |
| Prefect task integration | ⚠️ Requires wrapper around CLI or CDP |
| Resource efficiency | ✅ Much lighter than Chrome |
| Anti-bot bypass | ✅ Built-in stealth, better than vanilla Playwright |

### When to consider

- Sites with aggressive anti-bot that qcrawl's headless can't bypass
- Resource-constrained environments (ARM VM with limited RAM)
- High-concurrency scraping where Chrome's memory footprint is prohibitive

### When NOT to use

- Static sites (overkill, qcrawl HTTP is enough)
- When you need parsing logic (Obscura doesn't parse, only renders)
- If qcrawl + Playwright already works for your targets

**Conclusion:** Obscura replaces the *browser engine* layer, not the *parsing* layer.
Could be a drop-in for Playwright/Chrome in `WEB_DYNAMIC` connectors if needed.
Does NOT replace justhtml for extraction.

---

## Alternative Parsing Tools

### trafilatura

- **Purpose:** Content extraction (article body, metadata)
- **Pros:** Auto-detects main content, extracts title/date/author/tags
- **Cons:** Focused on articles, not structured event data
- **Fit:** ⚠️ Could help extract event descriptions, not full event structure

### readability-lxml

- **Purpose:** Article content extraction (Mozilla Readability port)
- **Pros:** Cleans boilerplate, navigation, ads
- **Cons:** Only extracts article body, loses surrounding context
- **Fit:** ❌ Too narrow for event parsing

### BeautifulSoup4

- **Purpose:** HTML parsing
- **Pros:** Large ecosystem, familiar API, CSS selectors
- **Cons:** Slower than justhtml, less tolerant of broken markup
- **Fit:** ⚠️ Viable fallback if justhtml has edge cases

### LLM-based extraction

- **Purpose:** Flexible extraction via prompts
- **Pros:** No selectors needed, adapts to layout changes
- **Cons:** Cost, latency, non-deterministic, requires API key
- **Fit:** ⚠️ Backup layer for sources where selectors are too fragile

### Comparison Matrix

| Tool | Parsing | JS render | Python native | Event-focused | Cost |
|------|---------|-----------|---------------|---------------|------|
| **justhtml** | ✅ | ❌ | ✅ | ⚠️ Generic | Free |
| **BeautifulSoup4** | ✅ | ❌ | ✅ | ⚠️ Generic | Free |
| **trafilatura** | ✅ | ❌ | ✅ | ❌ Articles | Free |
| **readability-lxml** | ✅ | ❌ | ✅ | ❌ Articles | Free |
| **LLM extraction** | ✅ | ❌ | ✅ | ✅ Flexible | Paid |
| **Obscura** | ❌ | ✅ | ⚠️ Subprocess/CDP | ❌ Browser | Free |

---

## Prefect Integration Design

### Flow structure (planned)

```python
@flow
async def run_all_sources():
    """Orchestrate ingestion of all active sources."""
    sources = await get_active_sources()
    for source in sources:
        run_source.submit(source.id)

@flow
async def run_source(source_id: str):
    """Orchestrate single source ingestion."""
    raw_docs = await fetch_documents(source_id)
    for doc in raw_docs:
        events = await extract_events(doc)
        await persist_events(events)

@task(retries=3, retry_delay_seconds=30, timeout_seconds=120)
async def fetch_documents(source_id: str) -> list[RawDocument]:
    """Fetch raw HTML/JSON from source."""
    # qcrawl HTTP or headless depending on source type
    ...

@task(retries=2, retry_delay_seconds=10, timeout_seconds=60)
async def extract_events(raw_doc: RawDocument) -> list[ParsedEventDTO]:
    """Parse HTML into domain DTOs."""
    # justhtml extraction logic
    ...
```

### Where Obscura would fit

```python
@task(retries=2, timeout_seconds=120)
async def fetch_with_obscura(url: str) -> str:
    """Fetch JS-rendered page via Obscura CDP."""
    # Option 1: subprocess CLI
    # Option 2: Playwright connecting to obscura serve
    ...
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-20 | Keep qcrawl + justhtml as primary stack | Covers all source types, Python-native, fits Prefect pattern |
| 2026-05-20 | Defer Obscura adoption | No anti-bot issues yet, qcrawl handles current targets |
| 2026-05-20 | Re-evaluate if sites require JS + anti-bot bypass | Obscura's stealth mode could solve hard cases |

## References

- Obscura: https://github.com/h4ckf0r0day/obscura
- qcrawl: [skill: scraping-qcrawl-justhtml]
- justhtml: [skill: scraping-qcrawl-justhtml]
- Prefect orchestration: [skill: prefect-orchestration-python]
