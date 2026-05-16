---
name: scraping-qcrawl-justhtml
version: 1
description: Skill for designing and reviewing ingestion connectors based on qcrawl and justhtml, separating crawling, parsing, and domain, supporting static websites, JS-heavy sites, feeds, and newsletters.
---

# Skill: scraping-qcrawl-justhtml

## Purpose

This skill guides Copilot when working with scraping/crawling and HTML/XML parsing in Python using qcrawl and justhtml.

Focus areas:

- Designing robust connectors for heterogeneous sources.
- Clearly separating crawling (download) from parsing (extraction) and from the domain.
- Handling real-world HTML (broken, changing) and sources without APIs.

## When to Use This Skill

Activate when the task involves:

- Creating or modifying a web source connector.
- Defining crawling pipelines with qcrawl.
- Choosing between plain HTTP and a headless browser for a given source.
- Parsing HTML with justhtml or XML/feeds.
- Designing extraction logic to domain DTOs (`RawDocumentDTO`, `EventDraft`, etc.).

## Default Decisions

- Crawling:
  - Framework: qcrawl for async crawling, queues, and middlewares.
  - HTTP download: use qcrawl's HTTP downloader when the page does not require JS.
  - JS download: use a headless/stealth browser (e.g. Camoufox/Playwright via qcrawl) only when necessary.

- HTML parsing:
  - Parser: justhtml for pure-Python HTML5, tolerant of broken markup.
  - Avoid relying on fragile structure; prefer robust strategies (text search, hierarchy, patterns).

- LLMs:
  - Use as an extra extraction/normalization layer when selectors are unreliable.
  - Do not replace basic deterministic parsing with prompts if it can be avoided.

## Connector Patterns

- Split into 3 layers:
  - `fetch` (crawling): returns HTML/JSON/raw bytes.
  - `parse` (extraction): transforms HTML/JSON into intermediate DTOs.
  - `map_to_domain`: projects DTOs to domain entities/value objects.

- Each connector must implement at minimum:
  - `fetch_raw_documents(source_config)`.
  - `extract_events(raw_document)`.

- Design connectors by source type:
  - `WEB_STATIC`: HTML without relevant JS.
  - `WEB_DYNAMIC`: requires JS (scroll, clicks, etc.).
  - `RSS/XML_FEED`.
  - `EMAIL_NEWSLETTER`: HTML bodies received via IMAP/webhook.

## Resilience to Change

- Do not rely solely on fragile CSS selectors or node indices.
- Combine:
  - Semantic selectors (known classes, roles, tags),
  - key-text search ("Date", "Location", etc.),
  - heuristics (first future `<time>`, first `<address>`, etc.).
- Log representative examples to make future adjustments easier.

## Error Handling and Limits

- Explicitly handle:
  - request timeouts,
  - DNS/HTTP errors,
  - unexpected redirects.
- Respect robots.txt and reasonable load limits (rate limiting, backoff).
- Design connectors to be idempotent: repeating a run must not duplicate events if the domain is well-designed.

## Domain Integration

- Connectors must produce DTOs (e.g. `RawDocumentDTO`, `ParsedEventDTO`) that the application/domain layer will persist or transform.
- Do not include business logic (e.g. deciding whether an event is valid) inside the connector — that belongs to the domain.

## Code Generation Rules

When the user asks for scraping/parsing code:

1. Start with the testing strategy: real HTML cases, edge cases, unusual newsletters.
2. Generate code using qcrawl for crawling and justhtml (or an appropriate parser) for parsing.
3. Clearly separate fetch, parse, and domain-mapping functions.
4. Include basic logging and error handling mechanisms.

## What to Avoid

- Mixing scraping, parsing, validation, and persistence in a single script.
- Relying exclusively on fragile selectors without logging or metrics.
- Using headless browsers by default when plain HTTP is sufficient.
- Aggressive scraping without rate limits or consideration for the target site's load.

## Recommended Tooling

- Install qcrawl, justhtml, and other scraping dependencies via **uv**.
- Use **ty** to type-check connectors and parsers.
- Use **Ruff** for linting and formatting all scraping/parsing code.
- Centralise commands in **mise** (`mise run scraping:test`, `mise run scraping:lint`, `mise run scraping:typecheck`).
