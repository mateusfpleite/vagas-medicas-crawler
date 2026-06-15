# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python web crawler that aggregates medical job postings from Brazilian job boards (Indeed, Vagas.com, BNE). Includes AI-powered enrichment via Google Gemini and PostgreSQL persistence on Supabase.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run all active spiders
vagas

# Run specific spiders
vagas indeed
vagas indeed vagas_com

# Dry run (print without saving to DB)
vagas --dry-run

# Run with AI enrichment
vagas --enrich

# Enrich existing vagas in DB (no crawling)
vagas --enrich-only
vagas --enrich-only --source indeed

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_normalize.py

# Run a single test
pytest tests/test_normalize.py::test_normalize_specialty -k "GINECOLOGISTA"

# Run integration tests only (hit external APIs)
pytest -m integration
```

## Architecture

**Pipeline**: Crawl → Normalize specialties → (Optional) AI Enrich → Upsert to PostgreSQL

### Core modules (`src/vagas/`)

- **cli.py** — Entry point. Orchestrates the pipeline: selects spiders, runs crawl, normalizes, optionally enriches, upserts.
- **models.py** — `Vaga` dataclass. Deduplication via `dedup_key()` (SHA256 of normalized title+company+location).
- **base_spider.py** — `BaseSpider` abstract class. All spiders implement `crawl() -> list[Vaga]`.
- **browser.py** — `stealth_page()` async context manager providing a Playwright page with stealth plugin.
- **normalize.py** — Deterministic specialty mapping (~50 variations → 31 canonical specialties). Strips gender markers, suffixes, typos.
- **enrich.py** — Gemini 2.5 Flash Lite batch enrichment. Determines if posting is for a physician, extracts specialty. Batches of 50, exponential backoff on rate limits.
- **storage.py** — PostgreSQL upsert with `ON CONFLICT (source, external_id)`. Loads `.env` lazily relative to source file.

### Spiders (`src/vagas/spiders/`)

| Spider | Source | Technique |
|--------|--------|-----------|
| `IndeedSpider` | indeed.com | 16 specialty queries, extracts from `window.mosaic` JS object |
| `VagasComSpider` | vagas.com.br | HTML parsing of listing + sequential detail page fetches |
| `BNESpider` | bne.com.br | FilterKey extraction + paginated API calls via browser |

`TrabalhaBrasilSpider` and `VagaMedicaSpider` exist but are inactive (not in `ALL_SPIDERS`).

### Database

Single `vagas` table on Supabase PostgreSQL. Unique constraint on `(source, external_id)`. Tracks `crawler_version` as MD5 hash of spider source file.

## Key Conventions

- All spiders are async (`async def crawl()`). CLI uses `asyncio.run()`.
- `pytest-asyncio` with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio` decorator.
- Integration tests are marked with `@pytest.mark.integration`.
- Environment variables (`DATABASE_URL`, `GEMINI_API_KEY`) loaded from `.env` at project root.
- Language: code is in English, domain data (specialties, job titles) is in Brazilian Portuguese.
