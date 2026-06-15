# InfoJobs Spider Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an InfoJobs spider that crawls www.infojobs.com.br for medical job postings and extracts structured data from JSON-LD on detail pages.

**Architecture:** Playwright browses listing pages with multiple specialty-specific search queries (like Indeed spider). Job IDs are extracted from listing HTML. A lightweight `is_medical_title()` pre-filter (from `vagas.filters`) removes non-medical results at the spider level, consistent with other spiders. Detail pages are fetched via `httpx` (no browser needed) and parsed for JSON-LD `JobPosting` schema.org data. Pages may contain multiple JSON-LD blocks (e.g. BreadcrumbList + JobPosting), so we iterate all blocks. The spider follows the same `BaseSpider` interface and `known_ids` pattern as existing spiders.

**Tech Stack:** Playwright (listing), httpx (detail), BeautifulSoup + json (JSON-LD parsing), pytest

---

## Context for the implementer

### Codebase patterns to follow

- **BaseSpider** (`src/vagas/base_spider.py`): All spiders extend this. Must implement `async def crawl(self, known_ids: set[str] | None = None) -> list[Vaga]`.
- **Vaga model** (`src/vagas/models.py`): Dataclass with fields: `title`, `location`, `source`, `url`, `company`, `salary`, `salary_min`, `salary_max`, `salary_period`, `job_type`, `specialty`, `external_id`, `description`, `benefits`, `published_at`, `raw_html`.
- **stealth_page()** (`src/vagas/browser.py`): Async context manager that yields a Playwright page with stealth plugin. Used by all browser-based spiders.
- **CLI registration** (`src/vagas/cli.py:18`): `ALL_SPIDERS = [IndeedSpider, VagasComSpider, BNESpider]` — new spider gets appended here.
- **known_ids pattern**: CLI passes `get_known_ids(conn, spider.name)` to `spider.crawl()`. Spider skips detail fetches for IDs already in DB. See BNE spider for reference.
- **Test pattern**: Tests use factory functions to build mock data and test the parser in isolation (no network). See `tests/test_spiders/test_indeed.py` for the canonical example.

### InfoJobs site structure

- **Listing URL**: `https://www.infojobs.com.br/empregos.aspx?palabra={query}` — needs JS rendering (Playwright).
- **Job card links**: `a[href*="/vaga-de-"]` — href contains slug + numeric ID: `/vaga-de-medico-ginecologista-em-sao-paulo__11310399.aspx`
- **Job ID extraction**: Numeric value between `__` and `.aspx` in URL. E.g. `11310399`.
- **Detail page**: `https://www.infojobs.com.br/vaga-de-{slug}__{id}.aspx` — contains `<script type="application/ld+json">` with schema.org `JobPosting`.
- **JSON-LD fields**: `title`, `description`, `datePosted`, `validThrough`, `employmentType`, `hiringOrganization.name`, `jobLocation.address.addressLocality`, `jobLocation.address.addressRegion`.
- **Salary**: Not in JSON-LD. Visible in listing card text as "R$ X a R$ Y" or "Salário a combinar".
- **No reliable pagination**: `Page=` URL param doesn't work consistently. Stick to first page per query (~20 results).
- **Anti-bot**: Light — Google Tag Manager, no Cloudflare. Playwright with stealth should work fine.

### Search queries

Use specialty-specific queries to maximize coverage (same strategy as Indeed):

```python
_SEARCH_QUERIES = [
    "médico",
    "médico clínico geral",
    "médico plantonista",
    "médico do trabalho",
    "médico pediatra",
    "médico ginecologista",
    "médico cardiologista",
    "médico ortopedista",
    "médico psiquiatra",
    "médico cirurgião",
    "médico intensivista",
    "médico anestesista",
    "médico dermatologista",
    "médico neurologista",
    "médico oftalmologista",
    "médico endocrinologista",
]
```

---

### Task 1: JSON-LD detail page parser

Parse a detail page's JSON-LD into Vaga fields. This is a pure function with no network calls — ideal to TDD first.

**Files:**
- Create: `src/vagas/spiders/infojobs.py`
- Create: `tests/test_spiders/test_infojobs.py`
- Create: `tests/fixtures/infojobs_detail.html`

**Step 1: Create the detail page fixture**

Save a realistic HTML fixture to `tests/fixtures/infojobs_detail.html`:

```html
<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">
{
  "@context": "http://schema.org",
  "@type": "JobPosting",
  "title": "Médico Ginecologista",
  "description": "Área e especialização profissional: Saúde - Ginecologia/Obstetrícia\nNível hierárquico: Especialista\nLugar de trabalho: São Paulo, SP\nRegime de contratação de tipo Efetivo – CLT\nJornada Período Integral\nMédico Ginecologista para atuação na Atenção Primária à Saúde.\nDisponibilidade para atuar 12h semanais.\nRegime de contratação CLT.\nRegião de atuação: Zona Leste SP.",
  "employmentType": "Jornada completa",
  "datePosted": "2026-01-30T08:00:00.0000000",
  "validThrough": "2026-05-01T08:00:00.0000000",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Santa Marcelina Saúde",
    "logo": "https://ncdn0.infojobs.com.br/logos/2015/08/05/391048.jpg"
  },
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressCountry": "BR",
      "addressLocality": "São Paulo",
      "addressRegion": "SP",
      "postalCode": "08270-070"
    }
  }
}
</script>
</head>
<body>
<h1>Médico Ginecologista - APS Santa Marcelina</h1>
<div class="job-detail">
  <span class="salary">Salário a combinar</span>
</div>
</body>
</html>
```

**Step 2: Write the failing tests**

Create `tests/test_spiders/test_infojobs.py`:

```python
import json
from pathlib import Path

from vagas.models import Vaga
from vagas.spiders.infojobs import InfoJobsSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_detail_extracts_jsonld():
    html = (FIXTURES / "infojobs_detail.html").read_text()
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico Ginecologista",
        location="Brasil",
        source="infojobs",
        url="https://www.infojobs.com.br/vaga-de-medico-ginecologista__11310399.aspx",
        external_id="11310399",
    )
    spider.parse_detail(html, vaga)

    assert vaga.company == "Santa Marcelina Saúde"
    assert vaga.location == "São Paulo, SP"
    assert vaga.job_type == "Jornada completa"
    assert "Ginecologista" in vaga.description
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 30
    assert vaga.raw_html == html


def test_parse_detail_no_jsonld():
    """Page without JSON-LD should not crash, just leave fields as-is."""
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__123.aspx", external_id="123",
    )
    spider.parse_detail("<html><body><p>No data</p></body></html>", vaga)
    assert vaga.company is None
    assert vaga.description is None
    assert vaga.raw_html is not None


def test_parse_detail_empty_organization():
    """Missing hiringOrganization should not crash."""
    html = '''<html><head><script type="application/ld+json">
    {"@type": "JobPosting", "title": "Médico", "description": "Desc"}
    </script></head><body></body></html>'''
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__456.aspx", external_id="456",
    )
    spider.parse_detail(html, vaga)
    assert vaga.company is None
    assert vaga.description == "Desc"


def test_parse_detail_multiple_jsonld_blocks():
    """JobPosting should be found even if BreadcrumbList comes first."""
    html = '''<html><head>
    <script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": []}
    </script>
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "Médico", "description": "Found it",
     "hiringOrganization": {"@type": "Organization", "name": "Hospital X"}}
    </script>
    </head><body></body></html>'''
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__789.aspx", external_id="789",
    )
    spider.parse_detail(html, vaga)
    assert vaga.description == "Found it"
    assert vaga.company == "Hospital X"
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/test_spiders/test_infojobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vagas.spiders.infojobs'`

**Step 4: Write minimal implementation**

Create `src/vagas/spiders/infojobs.py` with just the parser:

```python
import json
import logging
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.models import Vaga

log = logging.getLogger(__name__)

BASE_URL = "https://www.infojobs.com.br"

# Extract numeric job ID from URL: __11310399.aspx -> 11310399
_ID_RE = re.compile(r"__(\d+)\.aspx")


class InfoJobsSpider(BaseSpider):
    """
    Spider para o InfoJobs Brasil (infojobs.com.br).

    Listing: Playwright com queries de busca por especialidade.
    Detail: httpx GET + JSON-LD parsing.
    """

    name = "infojobs"

    @staticmethod
    def parse_detail(html: str, vaga: Vaga) -> None:
        """Enrich a Vaga in-place with JSON-LD data from the detail page."""
        vaga.raw_html = html
        soup = BeautifulSoup(html, "lxml")

        # Find JobPosting JSON-LD (may have multiple blocks: BreadcrumbList, etc.)
        data = None
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            if not ld_tag.string:
                continue
            try:
                parsed = json.loads(ld_tag.string)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
                data = parsed
                break

        if data is None:
            return

        # Description
        desc = data.get("description")
        if desc and isinstance(desc, str):
            vaga.description = desc.strip()

        # Company
        org = data.get("hiringOrganization")
        if isinstance(org, dict):
            name = org.get("name", "").strip()
            if name:
                vaga.company = name

        # Location
        loc = data.get("jobLocation")
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            city = addr.get("addressLocality", "").strip()
            state = addr.get("addressRegion", "").strip()
            if city and state:
                vaga.location = f"{city}, {state}"
            elif city:
                vaga.location = city

        # Employment type
        emp_type = data.get("employmentType")
        if emp_type and isinstance(emp_type, str):
            vaga.job_type = emp_type.strip()

        # Publication date
        date_str = data.get("datePosted")
        if date_str:
            vaga.published_at = _parse_iso_date(date_str)


def _parse_iso_date(s: str) -> datetime | None:
    """Parse ISO date like '2026-01-30T08:00:00.0000000'."""
    # Truncate to standard precision
    s = s.strip()[:19]
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_spiders/test_infojobs.py -v`
Expected: All 4 tests PASS

---

### Task 2: Listing page parser

Parse listing page HTML to extract job card URLs and IDs. Pure function, no browser needed for testing.

**Files:**
- Modify: `src/vagas/spiders/infojobs.py`
- Modify: `tests/test_spiders/test_infojobs.py`

**Step 1: Write the failing tests**

Append to `tests/test_spiders/test_infojobs.py`:

```python
def test_parse_listing_extracts_vagas():
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico-clinico-geral-em-sao-paulo__11310001.aspx">
      <h3>Médico Clínico Geral</h3>
    </a>
    <a href="/vaga-de-medico-pediatra-em-curitiba__11310002.aspx">
      <h3>Médico Pediatra</h3>
    </a>
    <a href="/vaga-de-analista-financeiro-em-bh__11310003.aspx">
      <h3>Analista Financeiro</h3>
    </a>
    </body></html>"""

    vagas = spider.parse_listing(html)
    # "Analista Financeiro" is filtered out by is_medical_title
    assert len(vagas) == 2
    assert vagas[0].title == "Médico Clínico Geral"
    assert vagas[0].external_id == "11310001"
    assert vagas[0].url == "https://www.infojobs.com.br/vaga-de-medico-clinico-geral-em-sao-paulo__11310001.aspx"
    assert vagas[0].source == "infojobs"
    assert vagas[1].title == "Médico Pediatra"
    assert vagas[1].external_id == "11310002"


def test_parse_listing_filters_non_medical():
    """Two-layer filter: allowlist (must contain 'médic') + blocklist (is_medical_title)."""
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico-geral__1.aspx"><h3>Médico Clínico Geral</h3></a>
    <a href="/vaga-de-balconista__2.aspx"><h3>Balconista De Medicamentos</h3></a>
    <a href="/vaga-de-veterinario__3.aspx"><h3>Médico Veterinário</h3></a>
    <a href="/vaga-de-enfermeiro__4.aspx"><h3>Enfermeiro Intensivista</h3></a>
    <a href="/vaga-de-psiquiatra__5.aspx"><h3>Médico Psiquiatra</h3></a>
    <a href="/vaga-de-docente__6.aspx"><h3>Docente Medicina Veterinária</h3></a>
    <a href="/vaga-de-auxiliar__7.aspx"><h3>Auxiliar de Consultório Médico</h3></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    titles = {v.title for v in vagas}
    # Should pass: real doctor titles
    assert "Médico Clínico Geral" in titles
    assert "Médico Psiquiatra" in titles
    # Blocked by allowlist (no "médic[oa]" word):
    assert "Balconista De Medicamentos" not in titles  # "medicamentos" != "médic"
    assert "Enfermeiro Intensivista" not in titles
    assert "Docente Medicina Veterinária" not in titles  # "medicina" != "médic[oa]"
    # Blocked by blocklist (is_medical_title):
    assert "Médico Veterinário" not in titles  # veterinário in blocklist
    assert "Auxiliar de Consultório Médico" not in titles  # auxiliar in blocklist


def test_parse_listing_empty():
    spider = InfoJobsSpider()
    vagas = spider.parse_listing("<html><body><p>No jobs</p></body></html>")
    assert vagas == []


def test_parse_listing_deduplicates_by_id():
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico__11310001.aspx"><h3>Médico A</h3></a>
    <a href="/vaga-de-medico-dup__11310001.aspx"><h3>Médico A Dup</h3></a>
    <a href="/vaga-de-medico-b__11310002.aspx"><h3>Médico B</h3></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    assert len(vagas) == 2
    ids = {v.external_id for v in vagas}
    assert ids == {"11310001", "11310002"}


def test_parse_listing_skips_no_id():
    """Links without __ID.aspx pattern should be skipped."""
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico__12345.aspx"><h3>Médico Geral</h3></a>
    <a href="/sobre-nos.aspx"><h3>Sobre Nós</h3></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico Geral"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spiders/test_infojobs.py::test_parse_listing_extracts_vagas -v`
Expected: FAIL with `AttributeError: 'InfoJobsSpider' object has no attribute 'parse_listing'`

**Step 3: Implement `parse_listing`**

Add imports at top of `src/vagas/spiders/infojobs.py`:

```python
from vagas.filters import is_medical_title
```

Add module-level regex (same as VagasComSpider — allowlist requiring "médic" in title):

```python
# Title must contain "médic" to be considered a doctor vacancy
_TITLE_MEDICAL_RE = re.compile(r"\bm[ée]dic[oa]?\b", re.IGNORECASE)
```

This creates a two-layer filter:
1. **Allowlist** (`_TITLE_MEDICAL_RE`): title must contain "médic" — rejects "Docente Medicina", "Biomédica Esteta", "Consultor Comercial"
2. **Blocklist** (`is_medical_title`): rejects known non-doctor patterns — catches "Médico Veterinário", "Promotor Médico", "Auxiliar Médico"

Add to `InfoJobsSpider` class:

```python
    def parse_listing(self, html: str) -> list[Vaga]:
        """Extract job cards from a listing page, filtering non-medical titles."""
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []
        seen_ids: set[str] = set()

        for link in soup.select('a[href*="/vaga-de-"]'):
            href = link.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue

            job_id = m.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title_el = link.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Two-layer filter: allowlist + blocklist (avoid detail fetches for non-doctors)
            if not _TITLE_MEDICAL_RE.search(title):
                continue
            if not is_medical_title(title):
                continue

            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            vagas.append(Vaga(
                title=title,
                location="Brasil",
                source=self.name,
                url=url,
                external_id=job_id,
            ))

        return vagas
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spiders/test_infojobs.py -v`
Expected: All 9 tests PASS

---

### Task 3: Crawl method

Wire listing + detail into the async `crawl()` method. Uses Playwright for listings and httpx for detail pages.

**Files:**
- Modify: `src/vagas/spiders/infojobs.py`

**Step 1: Implement `crawl()`**

Add imports at top of `infojobs.py` (final consolidated import block):

```python
import asyncio
import json
import logging
import random
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_page
from vagas.filters import is_medical_title
from vagas.models import Vaga
```

Add to `InfoJobsSpider` class:

```python
    WAIT_SELECTOR = 'a[href*="/vaga-de-"]'

    _SEARCH_QUERIES = [
        "médico",
        "médico clínico geral",
        "médico plantonista",
        "médico do trabalho",
        "médico pediatra",
        "médico ginecologista",
        "médico cardiologista",
        "médico ortopedista",
        "médico psiquiatra",
        "médico cirurgião",
        "médico intensivista",
        "médico anestesista",
        "médico dermatologista",
        "médico neurologista",
        "médico oftalmologista",
        "médico endocrinologista",
    ]

    async def crawl(self, known_ids: set[str] | None = None) -> list[Vaga]:
        seen_ids: set[str] = set()
        all_vagas: list[Vaga] = []

        # 1. Browse listing pages with multiple queries
        for query in self._SEARCH_QUERIES:
            url = f"{BASE_URL}/empregos.aspx?palabra={quote_plus(query)}"
            async with stealth_page() as page:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_selector(self.WAIT_SELECTOR, timeout=15000)
                    await asyncio.sleep(2)
                except Exception:
                    log.warning("[%s] failed/blocked for query '%s'", self.name, query)
                    continue

                html = await page.content()
                vagas = self.parse_listing(html)

                new = 0
                for v in vagas:
                    if v.external_id and v.external_id not in seen_ids:
                        seen_ids.add(v.external_id)
                        all_vagas.append(v)
                        new += 1

                log.info("[%s] query '%s': %d results (%d new)",
                         self.name, query, len(vagas), new)

            # Delay between queries
            await asyncio.sleep(2 + random.uniform(0.5, 1.5))

        log.info("[%s] total unique from listings: %d", self.name, len(all_vagas))

        # 2. Fetch detail pages via httpx (skipping known IDs)
        _known = known_ids or set()
        need_detail = [v for v in all_vagas if v.external_id not in _known]
        log.info("[%s] %d vagas need detail (%d already known)",
                 self.name, len(need_detail), len(all_vagas) - len(need_detail))

        fetched = 0
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
            follow_redirects=True,
            timeout=15.0,
        ) as client:
            for vaga in need_detail:
                try:
                    resp = await client.get(vaga.url)
                    if resp.status_code == 200:
                        self.parse_detail(resp.text, vaga)
                        fetched += 1
                    else:
                        log.warning("[%s] detail %s returned %d",
                                    self.name, vaga.url, resp.status_code)
                except Exception as e:
                    log.warning("[%s] detail failed %s: %s", self.name, vaga.url, e)

                await asyncio.sleep(1 + random.uniform(0.5, 1.0))

        log.info("[%s] details fetched: %d/%d", self.name, fetched, len(need_detail))
        log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
        return all_vagas
```

**Step 2: Verify existing tests still pass**

Run: `pytest tests/test_spiders/test_infojobs.py -v`
Expected: All 9 tests still PASS (crawl is async and not called by unit tests)

---

### Task 4: Register spider in CLI

**Files:**
- Modify: `src/vagas/cli.py:9-18`

**Step 1: Add import and register**

In `src/vagas/cli.py`, add the import:

```python
from vagas.spiders.infojobs import InfoJobsSpider
```

Update `ALL_SPIDERS`:

```python
ALL_SPIDERS = [IndeedSpider, VagasComSpider, BNESpider, InfoJobsSpider]
```

**Step 2: Verify import works**

Run: `python -c "from vagas.spiders.infojobs import InfoJobsSpider; print('OK')"`
Expected: `OK`

**Step 3: Verify all tests pass**

Run: `pytest tests/ -v`
Expected: All tests PASS

---

### Task 5: Dry-run integration test

Run the spider in `--dry-run` mode against the live site to validate end-to-end.

**Step 1: Run dry-run with only infojobs**

Run: `vagas infojobs --dry-run`

Expected output:
- Log lines showing queries being executed
- Log lines showing detail pages being fetched
- Printed vagas with titles like "Médico Ginecologista", "Médico Clínico Geral", etc.
- No crashes

**Step 2: Evaluate and fix issues**

Check:
- Are job titles being extracted correctly?
- Are detail pages returning JSON-LD data?
- Is `known_ids` skipping working? (won't skip anything on first run, but verify the log message)
- Are there excessive blocks/failures?

If the listing page CSS selector doesn't match, adjust `WAIT_SELECTOR` and `parse_listing` selectors based on actual HTML.

**Step 3: Run full pipeline dry-run**

Run: `vagas --dry-run`

Verify InfoJobs spider runs alongside Indeed, Vagas.com, and BNE without issues.
