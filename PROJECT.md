# Project: Flama Brand SEO, GEO & MCP AI Search Integration

## Architecture
Flama is a full-stack Japanese language learning platform (Flask REST API on port 4789, Flama Connect Yomitan/MCP bridge on port 4790, React 19 SPA frontend, Flama Audio desktop companion).

This project establishes Flama.vn as the authoritative brand entity across traditional search engines and AI generative engines (ChatGPT, Perplexity, Claude, Google AI Overviews), while exposing a secure, anti-scraping Model Context Protocol (MCP) public search endpoint for external AI agents.

### Subsystems:
1. **SEO Strategy Subsystem (`docs/seo/`)**:
   - Brand entity defense roadmap (`BRAND_ENTITY_SEO_STRATEGY.md`).
   - Keyword research matrix (`KEYWORD_RESEARCH_MATRIX.md`) with 50+ keywords across Brand and 4 feature clusters (SRS/Anki, Yomitan Mining, Local TTS, Marketplace & JLPT).
2. **Technical SEO & GEO Subsystem (`app/routes/seo.py`, `app/services/seo_service.py`, `app/spa.py`, `frontend/index.html`)**:
   - `GET /robots.txt`: Optimized crawler rules for GPTBot, PerplexityBot, ClaudeBot, Google-Extended, disallowing private app routes, linking to `sitemap.xml` and `llms.txt`.
   - `GET /sitemap.xml`: XML sitemap cataloging 38 authoritative public URLs with priority and change frequency.
   - `GET /llms.txt`: Machine-readable overview adhering to llmstxt.org linking core features, docs, and MCP endpoint.
   - `frontend/index.html`: Canonical link, OpenGraph, Twitter Cards, and Schema.org JSON-LD graph (`Organization`, `WebSite`, `SoftwareApplication` / `EducationalApplication`, `FAQPage`, `Course`).
3. **Model Context Protocol (MCP) Subsystem (`app/services/mcp/`, `app/connect/mcp.py`, `app/routes/mcp.py`, `scripts/flama_mcp_server.py`)**:
   - Public AI Search tools: `search_marketplace_decks`, `lookup_public_vocabulary`, `get_public_deck_preview` (sample preview only, max 5 cards), `get_flama_documentation`.
   - Strict Privacy Fence: Zero access to private user notes, study logs, or unshared decks.
   - Anti-Scraping Guardrail: Preview only (max 3-5 sample cards), strict pagination bounds (5-10 decks, max 20).
   - Transports: HTTP POST on `/api/mcp` and Stdio CLI server `scripts/flama_mcp_server.py`.
4. **E2E Testing & Verification Subsystem (`tests/`)**:
   - `tests/test_seo_routes.py` (robots.txt, sitemap.xml, llms.txt, SPA bypass).
   - `tests/test_mcp_public_search.py` (unauthenticated discovery, public deck queries, vocabulary lookups, docs, privacy leaks & anti-scraping bounds).
   - `tests/test_seo_adversarial.py`, `tests/test_mcp_adversarial_challenge.py`, `tests/test_schema_jsonld.py`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Brand Entity SEO Strategy | Roadmap for Organization schema, GSC, social linking, brand profile, entity defense | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Keyword Research Matrix | 50+ keywords across Brand and 4 feature clusters with Intent, Volume, Difficulty, Landing page | M1 | ORIGINAL_REQUEST §R1, R2 |
| 3 | Core Feature Intent Mapping | Topic clustering across SRS, Yomitan, Local TTS, Marketplace & JLPT | M1 | ORIGINAL_REQUEST §R2 |
| 4 | llms.txt Machine-Readable Spec | Standard llmstxt.org file serving overview, features, guide links, and MCP index | M2 | ORIGINAL_REQUEST §R3 |
| 5 | robots.txt AI Bot Optimization | Robots.txt with explicit allow/disallow for GPTBot, PerplexityBot, ClaudeBot, Google-Extended | M2 | ORIGINAL_REQUEST §R3 |
| 6 | Dynamic sitemap.xml | XML sitemap containing all 38 public indexable pages | M2 | ORIGINAL_REQUEST §R3 |
| 7 | On-Page Metadata (OG/Twitter/Canonical) | Meta tags for rich social snippets and canonical domain defense | M2 | ORIGINAL_REQUEST §R3 |
| 8 | Schema.org JSON-LD Structured Data | Validated JSON-LD (Organization, WebSite, SoftwareApplication, FAQPage, Course) | M2 | ORIGINAL_REQUEST §R3 |
| 9 | Public MCP Search Endpoint | MCP tools for public marketplace decks and vocabulary lookups | M3 | ORIGINAL_REQUEST §R4 |
| 10 | MCP Privacy Barrier | Strict isolation preventing access to private user notes or study logs | M3 | ORIGINAL_REQUEST Follow-up 1 |
| 11 | MCP Anti-Scraping Guardrail | Limit deck card returns to 3-5 preview samples and bound query limits | M3 | ORIGINAL_REQUEST Follow-up 2 |
| 12 | MCP Stdio CLI Transport | Standalone Python stdio server for desktop AI agents (Claude Desktop, Cursor) | M3 | ORIGINAL_REQUEST §R4 |
| 13 | MCP Automated Test Suite | Automated tests verifying MCP query response and security boundaries | M3 | ORIGINAL_REQUEST §R4 |
| 14 | E2E Integration Suite & Test Ready | Automated verification across SEO, GEO, Schema syntax, and MCP endpoints | M4 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status | Subagent / Outputs |
|---|------|-------|-------------|--------|---------------------|
| 1 | Strategy Deliverables | Create `docs/seo/BRAND_ENTITY_SEO_STRATEGY.md` and `docs/seo/KEYWORD_RESEARCH_MATRIX.md` | none | DONE | worker_m1: `docs/seo/BRAND_ENTITY_SEO_STRATEGY.md`, `docs/seo/KEYWORD_RESEARCH_MATRIX.md` (68 keywords) |
| 2 | Technical SEO & GEO Standards | Implement `app/services/seo_service.py`, `app/routes/seo.py`, `app/spa.py` bypass, `frontend/index.html` tags & schema, and `tests/test_seo_routes.py` | none | DONE | worker_m2: `app/services/seo_service.py`, `app/routes/seo.py`, `app/spa.py`, `frontend/index.html`, `tests/test_seo_routes.py` (6/6 tests pass) |
| 3 | MCP AI Search Integration | Implement `app/services/mcp/public_search_tools.py`, MCP registry update, auth bypass for public tools, anti-scraping limits, `scripts/flama_mcp_server.py`, and `tests/test_mcp_public_search.py` | none | DONE | worker_m3: `app/services/mcp/public_search_tools.py`, `app/connect/mcp.py`, `scripts/flama_mcp_server.py`, `tests/test_mcp_public_search.py` (10/10 tests pass) |
| 4 | E2E Verification & Forensic Audit | Run comprehensive test suites, validate Schema.org syntax, challenge edge cases, and run Forensic Integrity Audit | M1, M2, M3 | DONE | reviewer_1 (APPROVE), reviewer_2 (APPROVE), challenger_1 (APPROVE), challenger_2 (APPROVE), auditor_1 (CLEAN). GATE: PASS |

## Interface Contracts
### Flask SEO Blueprint (`app/routes/seo.py` ↔ `app/spa.py`)
- `GET /robots.txt` -> `text/plain; charset=utf-8`
- `GET /sitemap.xml` -> `application/xml; charset=utf-8`
- `GET /llms.txt` -> `text/plain; charset=utf-8`
- `app/spa.py`: `route_frontend_navigation()` bypasses paths `("/robots.txt", "/sitemap.xml", "/llms.txt")`.

### MCP Public Search (`app/services/mcp/public_search_tools.py` ↔ `app/connect/mcp.py`)
- `search_marketplace_decks(query: str, jlpt_level: str, category: str, limit: int, offset: int) -> dict`:
  - Returns `items`: list of deck metadata + `sample_preview` (strictly 3 to 5 sample cards).
  - Limit: default 10, max 20.
  - Queries strictly `DeckMarketplaceItem.publish_status == 'published'`.
- `lookup_public_vocabulary(query: str, jlpt_level: str, limit: int) -> dict`:
  - Returns matching words from published decks.
  - Limit: default 10, max 20.
- `get_flama_documentation(topic: str) -> dict`:
  - Returns machine-readable markdown for `overview`, `srs`, `yomitan`, `tts`, `marketplace`, `faq`.

## Code Layout
- Strategy documents: `docs/seo/`
- Backend SEO service & routes: `app/services/seo_service.py`, `app/routes/seo.py`
- SPA bypass: `app/spa.py`
- Frontend HTML & Schema: `frontend/index.html`
- MCP public tools: `app/services/mcp/public_search_tools.py`
- MCP registry & handler: `app/services/mcp_tool_registry.py`, `app/connect/mcp.py`
- MCP CLI script: `scripts/flama_mcp_server.py`
- Tests: `tests/test_seo_routes.py`, `tests/test_mcp_public_search.py`, `tests/test_schema_jsonld.py`, `tests/test_seo_adversarial.py`, `tests/test_mcp_adversarial_challenge.py`
