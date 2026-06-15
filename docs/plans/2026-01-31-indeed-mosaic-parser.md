# Indeed Mosaic Parser Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite IndeedSpider to extract structured job data from `window.mosaic.providerData` instead of parsing HTML cards + fetching detail pages (which are blocked by Cloudflare).

**Architecture:** The listing page embeds all job data in a JS object at `window.mosaic.providerData['mosaic-provider-jobcards'].metaData.mosaicProviderJobCardsModel.results`. We extract this via `page.evaluate()` — one page load, zero detail fetches. A new `parse_mosaic()` method replaces the old HTML-based `parse()`. We also add `salary_min`, `salary_max`, `salary_period`, and `benefits` fields to the `Vaga` model to hold the structured data Indeed provides.

**Tech Stack:** Python 3.13, Playwright + stealth, dataclasses, pytest

---

### Task 1: Add new fields to Vaga model

**Files:**
- Modify: `src/vagas/models.py:17-29`
- Modify: `tests/test_models.py`

**Step 1: Write failing tests for new fields**

Add to `tests/test_models.py`:

```python
def test_vaga_new_fields_default_none():
    v = Vaga(title="Médico", location="SP", source="indeed", url="http://x")
    assert v.salary_min is None
    assert v.salary_max is None
    assert v.salary_period is None
    assert v.benefits is None


def test_vaga_new_fields_populated():
    v = Vaga(
        title="Médico",
        location="SP",
        source="indeed",
        url="http://x",
        salary_min=15000.0,
        salary_max=30000.0,
        salary_period="MONTHLY",
        benefits=["Assistência médica", "Vale-transporte"],
    )
    assert v.salary_min == 15000.0
    assert v.salary_max == 30000.0
    assert v.salary_period == "MONTHLY"
    assert v.benefits == ["Assistência médica", "Vale-transporte"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py::test_vaga_new_fields_default_none tests/test_models.py::test_vaga_new_fields_populated -v`
Expected: FAIL with `TypeError: unexpected keyword argument`

**Step 3: Add fields to Vaga dataclass**

In `src/vagas/models.py`, add after line 27 (`description`), before `crawled_at`:

```python
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None  # "MONTHLY", "YEARLY", "HOURLY", etc.
    benefits: list[str] | None = None
```

The full field order becomes: title, location, source, url, company, salary, job_type, specialty, external_id, description, salary_min, salary_max, salary_period, benefits, crawled_at, raw_html.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: ALL PASS

**Step 5: Verify storage still excludes new fields correctly**

Run: `pytest tests/test_storage.py -v`
Expected: ALL PASS (new fields are just extra None values in JSON, no breakage)

---

### Task 2: Update storage serialization for new fields

**Files:**
- Modify: `src/vagas/storage.py:17-25`
- Modify: `tests/test_storage.py`

**Step 1: Write failing test for benefits serialization**

Add to `tests/test_storage.py`:

```python
def test_save_vaga_with_structured_salary(tmp_path):
    vaga = Vaga(
        title="Médico Offshore",
        location="Rio de Janeiro, RJ",
        source="indeed",
        url="https://br.indeed.com/viewjob?jk=abc",
        company="International SOS",
        external_id="abc123",
        salary="R$ 15.000 – R$ 30.000 por mês",
        salary_min=15000.0,
        salary_max=30000.0,
        salary_period="MONTHLY",
        job_type="Autônomo",
        benefits=["Assistência médica", "Seguro de vida"],
    )

    save_vaga(vaga, tmp_path)

    json_file = tmp_path / "indeed" / "abc123.json"
    meta = json.loads(json_file.read_text(encoding="utf-8"))
    assert meta["salary_min"] == 15000.0
    assert meta["salary_max"] == 30000.0
    assert meta["salary_period"] == "MONTHLY"
    assert meta["benefits"] == ["Assistência médica", "Seguro de vida"]
    assert meta["job_type"] == "Autônomo"
    assert "raw_html" not in meta
```

**Step 2: Run test to verify it passes (should already work)**

Run: `pytest tests/test_storage.py::test_save_vaga_with_structured_salary -v`
Expected: PASS — `asdict()` handles the new fields automatically. If it passes, this confirms no extra work needed in storage. If it fails, fix `_serialize_vaga` accordingly.

**Step 3: Run all storage tests**

Run: `pytest tests/test_storage.py -v`
Expected: ALL PASS

---

### Task 3: Rewrite IndeedSpider with mosaic extraction

This is the core task. Replace the HTML-based `parse()` + detail-fetching `crawl()` with a single `page.evaluate()` call.

**Files:**
- Modify: `src/vagas/spiders/indeed.py` (full rewrite)
- Modify: `tests/test_spiders/test_indeed.py` (new tests)

**Step 1: Write test for `parse_mosaic()` with mock data**

Replace the contents of `tests/test_spiders/test_indeed.py` with:

```python
import json

import pytest

from vagas.spiders.indeed import IndeedSpider


def _make_mosaic_result(**overrides):
    """Factory for a single mosaic result dict."""
    base = {
        "displayTitle": "Médico Clínico Geral",
        "company": "Hospital São Luiz",
        "formattedLocation": "São Paulo, SP",
        "jobLocationCity": "São Paulo",
        "jobLocationState": "SP",
        "jobkey": "abc123def456",
        "normTitle": "Medico",
        "jobTypes": ["Efetivo/CLT"],
        "salarySnippet": {
            "currency": "BRL",
            "text": "R$ 15.000 – R$ 30.000 por mês",
        },
        "extractedSalary": {"min": 15000, "max": 30000, "type": "MONTHLY"},
        "snippet": "<ul><li>Experiência em clínica médica</li></ul>",
        "taxonomyAttributes": [
            {
                "label": "benefits",
                "attributes": [
                    {"label": "Assistência médica", "suid": "X"},
                    {"label": "Vale-transporte", "suid": "Y"},
                ],
            },
            {"label": "remote", "attributes": []},
        ],
    }
    base.update(overrides)
    return base


def test_parse_mosaic_basic():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)

    assert len(vagas) == 1
    v = vagas[0]
    assert v.title == "Médico Clínico Geral"
    assert v.company == "Hospital São Luiz"
    assert v.location == "São Paulo, SP"
    assert v.source == "indeed"
    assert v.external_id == "abc123def456"
    assert v.url == "https://br.indeed.com/viewjob?jk=abc123def456"


def test_parse_mosaic_salary():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)

    v = vagas[0]
    assert v.salary == "R$ 15.000 – R$ 30.000 por mês"
    assert v.salary_min == 15000.0
    assert v.salary_max == 30000.0
    assert v.salary_period == "MONTHLY"


def test_parse_mosaic_no_salary():
    spider = IndeedSpider()
    results = [_make_mosaic_result(
        salarySnippet={"currency": "", "salaryTextFormatted": False},
        extractedSalary=None,
    )]
    vagas = spider.parse_mosaic(results)

    v = vagas[0]
    assert v.salary is None
    assert v.salary_min is None
    assert v.salary_max is None


def test_parse_mosaic_job_type():
    spider = IndeedSpider()
    results = [_make_mosaic_result(jobTypes=["Autônomo", "Freelancer"])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].job_type == "Autônomo, Freelancer"


def test_parse_mosaic_no_job_type():
    spider = IndeedSpider()
    results = [_make_mosaic_result(jobTypes=[])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].job_type is None


def test_parse_mosaic_benefits():
    spider = IndeedSpider()
    results = [_make_mosaic_result()]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].benefits == ["Assistência médica", "Vale-transporte"]


def test_parse_mosaic_no_benefits():
    spider = IndeedSpider()
    results = [_make_mosaic_result(taxonomyAttributes=[])]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].benefits is None


def test_parse_mosaic_description_from_snippet():
    spider = IndeedSpider()
    results = [_make_mosaic_result(
        snippet="<ul><li>Req 1</li><li>Req 2</li></ul>",
    )]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].description == "Req 1 Req 2"


def test_parse_mosaic_specialty_from_title():
    """normTitle 'Medico' + title has specialty -> extract it."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(displayTitle="Médico Cardiologista - Presencial"),
        _make_mosaic_result(displayTitle="Médico Generalista - Florianópolis"),
        _make_mosaic_result(displayTitle="Médico do Trabalho"),
        _make_mosaic_result(displayTitle="Médico"),
    ]
    vagas = spider.parse_mosaic(results)
    assert vagas[0].specialty == "Cardiologista"
    assert vagas[1].specialty == "Generalista"
    assert vagas[2].specialty == "do Trabalho"
    assert vagas[3].specialty is None


def test_parse_mosaic_multiple_results():
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(displayTitle="Médico A", jobkey="aaa"),
        _make_mosaic_result(displayTitle="Médico B", jobkey="bbb"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 2
    assert vagas[0].external_id == "aaa"
    assert vagas[1].external_id == "bbb"


def test_parse_mosaic_filters_non_medical():
    """normTitle != 'Medico' should be excluded."""
    spider = IndeedSpider()
    results = [
        _make_mosaic_result(normTitle="Medico", displayTitle="Médico Clínico"),
        _make_mosaic_result(normTitle="Professor De Educação Infantil", displayTitle="Professora Pedagoga"),
        _make_mosaic_result(normTitle="Advogado", displayTitle="Advogado Bancário"),
        _make_mosaic_result(normTitle="Veterinário", displayTitle="Médico Veterinário"),
    ]
    vagas = spider.parse_mosaic(results)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico Clínico"


def test_parse_mosaic_empty():
    spider = IndeedSpider()
    assert spider.parse_mosaic([]) == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spiders/test_indeed.py -v`
Expected: FAIL with `AttributeError: 'IndeedSpider' object has no attribute 'parse_mosaic'`

**Step 3: Implement `parse_mosaic()` and rewrite `crawl()`**

Replace `src/vagas/spiders/indeed.py` entirely:

```python
import asyncio
import logging
import re

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_page
from vagas.models import Vaga

log = logging.getLogger(__name__)

# JS snippet to extract job data from Indeed's mosaic provider
_MOSAIC_EXTRACT_JS = """() => {
    try {
        const pd = window.mosaic.providerData;
        const jc = pd['mosaic-provider-jobcards'];
        const model = jc.metaData.mosaicProviderJobCardsModel;
        return model.results.map(r => ({
            displayTitle: r.displayTitle || r.title || '',
            company: r.company || '',
            formattedLocation: r.formattedLocation || '',
            jobLocationCity: r.jobLocationCity || '',
            jobLocationState: r.jobLocationState || '',
            jobkey: r.jobkey || '',
            normTitle: r.normTitle || '',
            jobTypes: r.jobTypes || [],
            salarySnippet: r.salarySnippet || null,
            extractedSalary: r.extractedSalary || null,
            snippet: r.snippet || '',
            taxonomyAttributes: r.taxonomyAttributes || [],
        }));
    } catch (e) {
        return null;
    }
}"""

# Pattern: "Médico <specialty> - <suffix>" or "Médico <specialty>"
_SPECIALTY_RE = re.compile(
    r"^M[ée]dico(?:\(a\))?\s+(.+?)(?:\s*[-–|].+)?$",
    re.IGNORECASE,
)

# normTitle values we accept (case-insensitive comparison)
_MEDICAL_NORM_TITLES = {"medico"}


class IndeedSpider(BaseSpider):
    """
    Spider para o Indeed Brasil (br.indeed.com).

    Extrai dados estruturados de window.mosaic.providerData
    em vez de parsear HTML. Um único page load, zero fetches de detalhe.
    """

    name = "indeed"
    SEARCH_URL = "https://br.indeed.com/jobs?q=m%C3%A9dico&l="
    WAIT_SELECTOR = ".job_seen_beacon"
    BASE_URL = "https://br.indeed.com"

    def parse_mosaic(self, results: list[dict]) -> list[Vaga]:
        """Converte resultados do mosaic JS em lista de Vaga filtrada."""
        vagas: list[Vaga] = []

        for r in results:
            # Filter: only accept medical jobs
            norm = r.get("normTitle", "").strip().lower()
            if norm not in _MEDICAL_NORM_TITLES:
                continue

            title = r.get("displayTitle", "").strip()
            if not title:
                continue

            jobkey = r.get("jobkey", "")

            # Salary
            salary_text = None
            salary_min = None
            salary_max = None
            salary_period = None

            snippet_obj = r.get("salarySnippet") or {}
            if snippet_obj.get("text"):
                salary_text = snippet_obj["text"]

            extracted = r.get("extractedSalary")
            if extracted:
                raw_min = extracted.get("min")
                raw_max = extracted.get("max")
                if raw_min is not None and raw_min > 0:
                    salary_min = float(raw_min)
                if raw_max is not None and raw_max > 0:
                    salary_max = float(raw_max)
                salary_period = extracted.get("type")

            # Job type
            job_types = r.get("jobTypes") or []
            job_type = ", ".join(job_types) if job_types else None

            # Benefits from taxonomyAttributes
            benefits = None
            for attr in r.get("taxonomyAttributes") or []:
                if attr.get("label") == "benefits":
                    items = [a["label"] for a in attr.get("attributes", []) if "label" in a]
                    if items:
                        benefits = items
                    break

            # Description from snippet (strip HTML)
            snippet_html = r.get("snippet", "")
            description = None
            if snippet_html:
                soup = BeautifulSoup(snippet_html, "lxml")
                text = soup.get_text(separator=" ", strip=True)
                if text:
                    description = text

            # Specialty from title
            specialty = self._extract_specialty(title)

            vagas.append(
                Vaga(
                    title=title,
                    location=r.get("formattedLocation", "Brasil"),
                    source=self.name,
                    url=f"{self.BASE_URL}/viewjob?jk={jobkey}" if jobkey else "",
                    company=r.get("company") or None,
                    salary=salary_text,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_period=salary_period,
                    job_type=job_type,
                    specialty=specialty,
                    external_id=jobkey or None,
                    description=description,
                    benefits=benefits,
                )
            )

        log.info("Indeed parse_mosaic: %d vagas (from %d results)", len(vagas), len(results))
        return vagas

    @staticmethod
    def _extract_specialty(title: str) -> str | None:
        """Extrai especialidade do título. Ex: 'Médico Cardiologista' -> 'Cardiologista'."""
        m = _SPECIALTY_RE.match(title.strip())
        if not m:
            return None
        specialty = m.group(1).strip()
        # Skip generic suffixes that aren't specialties
        if not specialty or specialty.lower() in ("", "offshore"):
            return None
        return specialty

    async def crawl(self) -> list[Vaga]:
        async with stealth_page() as page:
            try:
                await page.goto(self.SEARCH_URL, wait_until="domcontentloaded")
                await page.wait_for_selector(self.WAIT_SELECTOR, timeout=20000)
                await asyncio.sleep(2)
            except Exception:
                log.warning("%s blocked or failed -- skipping", self.name)
                return []

            # Extract structured data from mosaic JS object
            results = await page.evaluate(_MOSAIC_EXTRACT_JS)
            if not results:
                log.warning("[%s] Could not extract mosaic data", self.name)
                return []

            log.info("[%s] Extracted %d results from mosaic", self.name, len(results))
            return self.parse_mosaic(results)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_spiders/test_indeed.py -v`
Expected: ALL PASS

**Step 5: Run entire test suite**

Run: `pytest -v`
Expected: ALL PASS

---

### Task 4: E2E validation

Run the spider against the live Indeed site to verify data quality.

**Step 1: Dry run**

Run: `python -m vagas.cli indeed --dry-run`

Expected output: a list of medical vagas with `[-]` indicators (no raw_html since we extract structured data, not HTML). All should have titles like "Médico ...", no "Professor", "Advogado", etc. Non-medical noise should be filtered out.

**Step 2: Full run and inspect output**

Run: `python -m vagas.cli indeed`

Then inspect a saved JSON file:

```bash
cat data/indeed/*.json | python -m json.tool | head -60
```

Expected: JSON files with populated `salary_min`, `salary_max`, `salary_period`, `job_type`, `benefits`, `specialty`, and `description` fields (some may be null depending on the job).

**Step 3: Verify no HTML files are created**

Since we no longer fetch detail pages, no `.html` files should be created for Indeed:

```bash
ls data/indeed/*.html 2>/dev/null && echo "UNEXPECTED: HTML files found" || echo "OK: No HTML files"
```

Expected: `OK: No HTML files`

---

### Task 5: Clean up old data files

The old spider created `.html` (Cloudflare challenge pages) and `.json` files with incomplete data. Delete them before the E2E run populates fresh data.

**Step 1: Delete old Cloudflare HTML files**

```bash
rm -f data/indeed/*.html
```

**Step 2: Delete old JSON files (stale data from old parser)**

```bash
rm -f data/indeed/*.json
```

Note: Task 3 already replaced `indeed.py` entirely (removing old `parse()` and `_full_url()`), and replaced the test file. No code cleanup needed here.
