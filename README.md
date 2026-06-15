# vagas-médicas

> The crawling & enrichment backend behind **[EmpregaMed](https://empregamed.com.br)** — an aggregator of medical job postings in Brazil.

A Python web crawler that scrapes physician job openings from Brazilian job boards, filters out the noise (non-doctor roles, stale listings, duplicates), enriches each posting with AI, and persists a clean, deduplicated dataset to PostgreSQL.

It is built to deal with the messy reality of Brazilian job boards: JavaScript-rendered listings, Cloudflare and reCAPTCHA, undocumented internal APIs, inconsistent specialty naming, and a lot of postings that mention *"médico"* but aren't actually for doctors.

> The public-facing website (Next.js) lives in a separate repo: [`mateusfpleite/vagas-medicas`](https://github.com/mateusfpleite/vagas-medicas).

---

## Pipeline at a glance

```
                ┌─────────┐   ┌──────────┐   ┌─────┐   ┌──────────┐   ┌─────┐   ┌────────┐
  per spider →  │  CRAWL  │ → │ SKIP     │ → │SCORE│ → │NORMALIZE │ → │ AI  │ → │ UPSERT │ → DB
                │ listing │   │ known    │   │ +   │   │specialty │   │enrich│  │ Postgres│
                │ +detail │   │ ids      │   │filter│  │+location │   │(opt)│   │+dedup  │
                └─────────┘   └──────────┘   └─────┘   └──────────┘   └─────┘   └────────┘
```

1. **Crawl** — each spider fetches listings (and detail pages where needed) for ~16 specialty queries.
2. **Skip known IDs** — anything already stored (or already discarded) is skipped before any expensive detail fetch.
3. **Score & filter** — a deterministic blocklist + a probabilistic medical score drop non-doctor postings.
4. **Normalize** — specialty names and locations are mapped to canonical values.
5. **AI enrich** *(optional)* — Gemini confirms the posting is for a physician and extracts the specialty when deterministic rules can't.
6. **Upsert & dedup** — rows are upserted into PostgreSQL and duplicates are collapsed.

---

## Sources

| Spider | Source | Technique |
|---|---|---|
| `indeed` | indeed.com | Playwright renders the page; job data is pulled straight from the `window.mosaic.providerData` JS object via an injected script, plus `normTitle` heuristics. |
| `vagas_com` | vagas.com.br | Playwright + stealth (site is behind Cloudflare). Parses `li.vaga` cards, clicks *"mostrar mais"* pagination, then fetches detail pages sequentially. |
| `bne` | bne.com.br | Extracts a `filterKey` (UUID) from the page, then drives the site's paginated internal JSON API (`/api/v1/Lists/SequenceJobs`). City-by-city searches; raw HTML is stored for offline re-parsing. |
| `infojobs` | infojobs.com.br | Playwright for the listing (specialty queries); detail pages fetched with `httpx` and parsed from **JSON-LD**. |
| `pci` | pciconcursos.com.br | `httpx`-only (static HTML, no anti-bot). Targets public *concursos* / *processos seletivos* with medical positions. |
| `gupy` | gupy.io | Talks directly to the public Gupy JSON API (`portal.api.gupy.io/api/job`); maps full state names → UF codes. |

> `trabalha_brasil` and `vagamedica` spiders also exist but are **inactive** (reCAPTCHA v3 and low-value source, respectively) — they're kept as best-effort references and are not in `ALL_SPIDERS`.

---

## Scraping strategy

**Right tool per site.** Static pages use plain `httpx`; JS-heavy or protected pages use **Playwright + [playwright-stealth](https://pypi.org/project/playwright-stealth/)**. When a site exposes an internal API (BNE, Gupy), the crawler skips HTML entirely and calls the API directly — faster and far more robust than DOM scraping.

**Bandwidth-aware rendering.** The Playwright layer blocks images, CSS, fonts and media, plus known analytics/telemetry domains (GTM, Clarity, PostHog…), so headless runs stay lean.

**Adaptive proxy fallback.** Every spider tracks consecutive failures. After a threshold (3), it transparently switches to a configured `PROXY_URL` for the rest of the run — no proxy traffic is spent unless a site actually starts blocking.

**Don't re-do work.** Before fetching detail pages, the crawler loads the set of already-known IDs (both stored vagas and previously *discarded* ones) and skips them. This makes incremental runs cheap and keeps detail-page traffic to a minimum.

**Survives long crawls.** The PostgreSQL connection is health-checked and transparently reconnected (`ensure_alive`) between spiders and around long-running enrichment, so a single stale socket doesn't sink a multi-source run.

---

## Quality: turning noise into a clean dataset

Brazilian boards return a lot of false positives for *"médico"* (vets, nurses, pharma sales reps, *"médico do trabalho"* admin roles…). Quality is enforced in layers, cheapest first:

1. **Title blocklist** (`filters.py`) — rejects clearly non-doctor titles (veterinário, enfermeiro, farmacêutico, técnico, vendedor…). Conservative: ambiguous titles are kept for later stages.
2. **Probabilistic scoring** (`scoring.py`) — a `medical_score` over title + description with two gates: a permissive pre-detail threshold (`0.4`) and a stricter post-detail one (`0.5`).
3. **AI enrichment** (`enrich.py`, optional) — **Gemini 2.5 Flash Lite**, batched 50 postings/call with exponential backoff on rate limits. It decides whether a posting is really for a physician and picks the specialty from a **fixed canonical list** (or returns null). Non-doctors are deleted and remembered in a `discarded_ids` table so they're never re-processed.

**Normalization**
- **Specialties** — a deterministic map (`normalize.py`) collapses ~50 variants into canonical specialties, stripping gender markers (`(a)`/`(o)`), context suffixes (*Presencial*, *Telemedicina*, …) and common typos.
- **Locations** — parsed against the official **IBGE municipalities** dataset; `"City - UF"` patterns are validated and split into `city` / `state`.
- **Deduplication** — a `dedup_key` (SHA-256 of normalized title + company + location) collapses the same posting appearing across sources.

---

## Data model

A single `vagas` table on **Supabase PostgreSQL**, with `UNIQUE (source, external_id)` driving idempotent `ON CONFLICT` upserts. A companion `discarded_ids` table records why a posting was dropped (`scoring`, `non_doctor`). Each row tracks a `crawler_version` (MD5 of the spider's source file) so you can tell which version of a spider produced it.

Run `vagas --stats` for an at-a-glance dashboard: counts by source, missing-field coverage, top specialties and cities, posting age distribution, and recent activity.

---

## Tech stack

- **Python 3.12+**, fully `asyncio`-based
- **Playwright** + **playwright-stealth** — headless browser automation
- **httpx** — async HTTP for APIs and static pages
- **BeautifulSoup4** + **lxml** — HTML parsing
- **psycopg 3** — PostgreSQL driver (Supabase)
- **google-genai** — Gemini for AI enrichment
- **pytest** + **pytest-asyncio** — tests (`asyncio_mode = "auto"`)

---

## Getting started

```bash
# Install (with dev dependencies) and the Playwright browser
pip install -e ".[dev]"
playwright install chromium
```

Create a `.env` at the project root:

```dotenv
DATABASE_URL=postgresql://user:password@host:5432/dbname
GEMINI_API_KEY=your-gemini-key      # only needed for --enrich / --enrich-only
PROXY_URL=http://user:pass@host:port # optional — used as fallback when a site blocks
```

---

## Usage

```bash
# Run all active spiders
vagas

# Run specific spiders
vagas indeed
vagas indeed vagas_com

# Print results without writing to the DB
vagas --dry-run

# Crawl + AI enrichment
vagas --enrich

# Target specific locations (repeatable)
vagas --location "Rio de Janeiro, RJ" --location "Campinas, SP"
```

Maintenance / backfill commands:

```bash
vagas --enrich-only [--source indeed]   # enrich existing rows, no crawling
vagas --normalize-locations             # backfill city/state from raw location
vagas --deduplicate                     # collapse duplicates in the DB
vagas --reparse                         # re-parse BNE rows from stored raw HTML
vagas --fetch-ibge                      # refresh the IBGE municipalities cache
vagas --stats                           # print the database dashboard
```

---

## Testing

```bash
pytest tests/                 # unit tests (fast, offline, fixture-driven)
pytest -m integration         # integration tests that hit external APIs
pytest tests/test_normalize.py::test_normalize_specialty -k "GINECOLOGISTA"
```

Spider parsers are tested against captured HTML/JSON fixtures in `tests/fixtures/`, so the parsing logic is covered without network access.

---

## Project layout

```
src/vagas/
├── cli.py            # entry point — orchestrates the whole pipeline
├── base_spider.py    # BaseSpider (proxy fallback, crawl contract)
├── browser.py        # Playwright + stealth context, resource blocking
├── models.py         # Vaga dataclass + dedup_key()
├── filters.py        # deterministic title blocklist
├── scoring.py        # probabilistic medical scoring
├── normalize.py      # specialty normalization (~50 → canonical)
├── location.py       # IBGE-based location parsing
├── enrich.py         # Gemini batch enrichment
├── storage.py        # PostgreSQL upsert / dedup / stats helpers
└── spiders/          # one module per source
```

---

## Notes

This project scrapes public job listings for aggregation. Be a good citizen: respect each site's terms of service and rate limits, and use the proxy/throttling features responsibly.
```
