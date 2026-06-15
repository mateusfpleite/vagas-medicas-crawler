# PCI Concursos Spider Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a spider for pciconcursos.com.br to crawl public concursos/processos seletivos for medical positions — filling our biggest coverage gap (interior/municipal government jobs across 20+ Brazilian states).

**Architecture:** httpx-only spider (no Playwright — site is static HTML, no anti-bot). Two-phase crawl: listing pages at `/vagas/medico-{specialty}` yield links to detail pages at `/noticias/{slug}`. Detail pages have JSON-LD `NewsArticle` with `datePublished` and `<div itemprop="articleBody">` with full position lists.

**Tech Stack:** httpx, BeautifulSoup (lxml), existing BaseSpider/Vaga infrastructure.

---

### Task 0a: Add `is_medical_title()` to post-crawl pipeline

**Problem:** `cli.py:76-78` only calls `medical_score()` in the post-crawl filter. The blocklist in `filters.py` (veterinário, enfermeiro, etc.) is never applied centrally — each spider must import and call it individually. `medical_score("Médico Veterinário")` = 0.9 (passes), but `is_medical_title("Médico Veterinário")` = False (blocked). Without this fix, any new spider without its own filter will leak non-doctor titles.

**Files:**
- Modify: `src/vagas/cli.py:1-2,76-78`
- Modify: `tests/test_scoring.py` (add a test verifying the combined filter)

**Step 1: Write test**

Add to `tests/test_scoring.py`:

```python
def test_veterinary_caught_by_combined_filter():
    """is_medical_title blocks titles that medical_score lets through."""
    from vagas.filters import is_medical_title
    from vagas.scoring import medical_score, FULL_THRESHOLD

    # medical_score alone passes "Médico Veterinário" (0.9 >= 0.5)
    assert medical_score("Médico Veterinário") >= FULL_THRESHOLD
    # But is_medical_title catches it
    assert is_medical_title("Médico Veterinário") is False
```

**Step 2: Add import in cli.py**

Add to imports (after line 8):
```python
from vagas.filters import is_medical_title
```

**Step 3: Update scoring filter in cli.py**

Change lines 76-78 from:
```python
            scoring_discarded = [
                v for v in vagas
                if medical_score(v.title, v.description) < FULL_THRESHOLD
            ]
```
to:
```python
            scoring_discarded = [
                v for v in vagas
                if not is_medical_title(v.title)
                or medical_score(v.title, v.description) < FULL_THRESHOLD
            ]
```

**Step 4: Run tests**

Run: `pytest tests/test_scoring.py tests/test_filters.py -v`
Expected: All PASSED

**Step 5: Commit**

```
fix: add is_medical_title blocklist to post-crawl pipeline
```

---

### Task 0b: Handle bare UF codes in `parse_location()` and `normalize_location()`

**Problem:** When a spider outputs bare state codes like "MG" (no city), `parse_location("MG")` returns `("MG", None)` instead of `(None, "MG")`. Then IBGE lookup for city "MG" fails and state info is lost entirely. Additionally, even after fixing `parse_location`, `normalize_location()` at line 140 returns `(None, None)` when `city is None`, discarding the state. Both functions must be fixed.

**Files:**
- Modify: `src/vagas/location.py:62-63` (parse_location)
- Modify: `src/vagas/location.py:140-141` (normalize_location)
- Modify: `tests/test_location.py`

**Step 1: Add test cases for both functions**

Add to `test_parse_location` parametrize list in `tests/test_location.py`:

```python
    # Bare UF codes (PCI spider fallback)
    ("MG", (None, "MG")),
    ("SP", (None, "SP")),
    ("rj", (None, "RJ")),
```

Add to `test_normalize_location` parametrize list in `tests/test_location.py`:

```python
    # Bare UF codes — state preserved even without city
    ("MG", (None, "MG")),
    ("SP", (None, "SP")),
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_location.py::test_parse_location tests/test_location.py::test_normalize_location -v`
Expected: FAIL on bare UF cases — `parse_location("MG")` returns `("MG", None)`, `normalize_location("MG")` returns `(None, None)`

**Step 3: Fix parse_location**

In `src/vagas/location.py`, change lines 62-63 from:
```python
    # No separator found — city-only input
    return cleaned, None
```
to:
```python
    # No separator found — check if it's a bare UF code
    if cleaned.upper() in _VALID_UFS:
        return None, cleaned.upper()
    return cleaned, None
```

**Step 4: Fix normalize_location**

In `src/vagas/location.py`, change lines 140-141 from:
```python
    if city is None:
        return None, None
```
to:
```python
    if city is None:
        return None, uf
```

This preserves the state when `parse_location` returns `(None, "MG")` — `normalize_location` will now return `(None, "MG")` instead of `(None, None)`.

**Step 5: Run tests**

Run: `pytest tests/test_location.py -v`
Expected: All PASSED

**Step 6: Commit**

```
fix: recognize bare UF codes in parse_location and preserve state in normalize_location
```

---

### Task 1: Write listing parser tests

**Files:**
- Create: `tests/test_spiders/test_pci.py`

**Step 1: Write the failing tests**

```python
from vagas.models import Vaga
from vagas.spiders.pci import PCISpider


def test_parse_listing_extracts_cards():
    """All three card classes (da, na, ea) are captured."""

    spider = PCISpider()
    # da = highlighted/sponsored, na = normal/recent, ea = older entries
    html = """<html><body><div id="concursos">
<div class="da" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-lavras-mg-abre-169-vagas" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-lavras-mg-abre-169-vagas" title="Prefeitura de Lavras - MG abre 169 vagas" rel="bookmark" style="display:block;">Prefeitura de Lavras</a>
<div class="cb"><img src="data:image/png;base64,x" class="lazyload"></div>
<div class="cc">MG</div>
<div class="cd">169 vagas até R$ 5.286,42<br><span>Vários Cargos<br><span>Superior</span></span></div>
<div class="ce"><span>16/03 a<br>16/04/2026</span></div>
<div class="clear"></div></div></div>
<div class="na" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-vitorino-pr-abre-concurso" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-vitorino-pr-abre-concurso" title="Prefeitura de Vitorino - PR abre concurso" rel="bookmark" style="display:block;">Prefeitura de Vitorino</a>
<div class="cc">PR</div>
<div class="cd">64 vagas até R$ 20.945,34<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div>
<div class="ea" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-cardoso-sp-concurso" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-cardoso-sp-concurso" title="Prefeitura de Cardoso - SP abre concurso" rel="bookmark" style="display:block;">Prefeitura de Cardoso</a>
<div class="cc">SP</div>
<div class="cd">62 vagas até R$ 7.602,95<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div>
</div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 3

    assert vagas[0].external_id == "prefeitura-de-lavras-mg-abre-169-vagas"
    assert vagas[0].company == "Prefeitura de Lavras"
    assert vagas[0].location == "MG"
    assert vagas[0].salary_max == 5286.42
    assert vagas[0].salary == "até R$ 5.286,42"
    assert vagas[0].source == "pci"

    assert vagas[1].external_id == "prefeitura-de-vitorino-pr-abre-concurso"
    assert vagas[1].location == "PR"
    assert vagas[1].salary_max == 20945.34

    assert vagas[2].external_id == "prefeitura-de-cardoso-sp-concurso"
    assert vagas[2].location == "SP"
    assert vagas[2].salary_max == 7602.95


def test_parse_listing_handles_cr_salary():
    """Salary with '+ CR' (cadastro reserva) is parsed correctly."""
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="na" data-url="https://www.pciconcursos.com.br/noticias/xaxim-sc">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/xaxim-sc" title="X" style="display:block;">Prefeitura de Xaxim</a>
<div class="cc">SC</div>
<div class="cd">5 vagas + CR até R$ 15.486,24<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div></div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].salary_max == 15486.24


def test_parse_listing_handles_cadastro_reserva_no_count():
    """'Cadastro reserva até R$ X' without vacancy count."""
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="ea" data-url="https://www.pciconcursos.com.br/noticias/tijucas-sc">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/tijucas-sc" title="X" style="display:block;">Prefeitura de Tijucas</a>
<div class="cc">SC</div>
<div class="cd">Cadastro reserva até R$ 21.773,73<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div></div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].salary_max == 21773.73


def test_parse_listing_deduplicates_by_slug():
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="na" data-url="https://www.pciconcursos.com.br/noticias/same-slug">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/same-slug" title="A" style="display:block;">A</a>
<div class="cc">SP</div><div class="cd">5 vagas até R$ 10.000,00</div>
<div class="clear"></div></div></div>
<div class="ea" data-url="https://www.pciconcursos.com.br/noticias/same-slug">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/same-slug" title="A dup" style="display:block;">A dup</a>
<div class="cc">SP</div><div class="cd">5 vagas até R$ 10.000,00</div>
<div class="clear"></div></div></div>
</div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1


def test_parse_listing_empty_page():
    spider = PCISpider()
    vagas = spider.parse_listing("<html><body><div id='concursos'></div></body></html>")
    assert vagas == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_spiders/test_pci.py -v`
Expected: `ModuleNotFoundError: No module named 'vagas.spiders.pci'`

**Step 3: Commit**

```
test: add listing parser tests for PCI Concursos spider
```

---

### Task 2: Write detail parser tests

**Files:**
- Modify: `tests/test_spiders/test_pci.py`

**Step 1: Append detail parser tests**

```python
def test_parse_detail_extracts_jsonld_and_location():
    html = """<html><head>
<script type="application/ld+json" class="yoast-schema-graph">{"@context":"https://schema.org","@graph":[
{"@type":"NewsArticle","headline":"Prefeitura de Machado - MG abre Processo Seletivo",
 "datePublished":"2026-01-12T19:12:56-03:00","dateModified":"2026-01-12T19:12:56-03:00",
 "publisher":{"@id":"https://www.pciconcursos.com.br/#organization"}},
{"@type":"Organization","name":"PCI Concursos"}
]}</script></head><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Machado - MG abre Processo Seletivo para Médico Clínico Geral</h1>
<abbr class="published" title="2026-01-12T19:12:56-03:00">12 de janeiro de 2026</abbr>
<div itemprop="articleBody">
<p>A Prefeitura de Machado anunciou abertura do Processo Seletivo.</p>
<ul><li>Médico Clínico Geral (1 vaga)</li></ul>
<p>A remuneração mensal é de R$ 14.746,36.</p>
</div></article>
<aside id="links"><ul>
<li class="pdf"><a href="https://arq.pciconcursos.com.br/edital.pdf" title="EDITAL">EDITAL DE ABERTURA</a></li>
</ul></aside></body></html>"""

    vaga = Vaga(
        title="Prefeitura de Machado",
        location="MG",
        source="pci",
        url="https://www.pciconcursos.com.br/noticias/prefeitura-de-machado-mg",
        external_id="prefeitura-de-machado-mg",
    )
    result = PCISpider.parse_detail(html, vaga)

    assert result is True
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 12
    assert vaga.location == "Machado, MG"
    assert vaga.description is not None
    assert "R$ 14.746,36" in vaga.description
    assert vaga.raw_html == html


def test_parse_detail_multi_position_with_medical():
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Vitorino - PR abre concurso</h1>
<abbr class="published" title="2026-02-02T17:39:06-03:00">2 de fevereiro de 2026</abbr>
<div itemprop="articleBody">
<p>Vagas para diversos cargos:</p>
<ul>
<li>Agente de Saúde (5 vagas)</li>
<li>Enfermeiro II</li>
<li>Médico Clínico Geral II</li>
<li>Médico Ginecologista e Obstetra</li>
<li>Médico Pediatra</li>
<li>Médico Veterinário (1 vaga)</li>
<li>Psicólogo</li>
</ul>
<p>Remuneração de R$ 1.669,91 a R$ 20.945,34 mensais.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Prefeitura de Vitorino",
        location="PR",
        source="pci",
        url="https://www.pciconcursos.com.br/noticias/test",
        external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)

    assert result is True
    assert vaga.location == "Vitorino, PR"
    assert vaga.description is not None
    assert vaga.published_at is not None


def test_parse_detail_only_veterinary_returns_false():
    """Médico Veterinário without human doctor positions is rejected."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Teste - SP abre concurso</h1>
<div itemprop="articleBody">
<p>Vagas:</p>
<ul>
<li>Médico Veterinário (2 vagas)</li>
<li>Auxiliar Administrativo (3 vagas)</li>
</ul>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False


def test_parse_detail_no_medical_positions_returns_false():
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Teste - SP abre concurso</h1>
<div itemprop="articleBody">
<p>Vagas para cargos administrativos:</p>
<ul>
<li>Auxiliar Administrativo (3 vagas)</li>
<li>Motorista (2 vagas)</li>
</ul>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False
    # Description must NOT be set when returning False (filter depends on this)
    assert vaga.description is None


def test_parse_detail_no_article_body_returns_false():
    html = "<html><body><h1>Empty page</h1></body></html>"
    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False


def test_parse_detail_fallback_to_abbr_date():
    """When JSON-LD is missing, falls back to abbr.published."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Ipê - RS abre processo</h1>
<abbr class="published" title="2026-01-28T16:16:16-03:00">28 de janeiro de 2026</abbr>
<div itemprop="articleBody">
<p>Vagas para Médico PSF.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="RS", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is True
    assert vaga.published_at is not None
    assert vaga.published_at.day == 28
    assert vaga.location == "Ipê, RS"


def test_parse_detail_location_hospital():
    """Location extracted from hospital headlines."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Hospital Beneficente Dr. César Santos de Passo Fundo - RS abre processo</h1>
<div itemprop="articleBody">
<p>Vagas para Médico Plantonista.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="RS", source="pci",
        url="https://test.com", external_id="test",
    )
    PCISpider.parse_detail(html, vaga)
    assert vaga.location == "Passo Fundo, RS"


def test_parse_detail_location_no_state_keeps_original():
    """Headlines without '- UF' pattern keep listing state."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">AgSUS reabre Processo Seletivo com diversas oportunidades</h1>
<div itemprop="articleBody">
<p>Vagas para Médico em todo o Brasil.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="Brasil", source="pci",
        url="https://test.com", external_id="test",
    )
    PCISpider.parse_detail(html, vaga)
    assert vaga.location == "Brasil"  # unchanged
```

**Step 2: Run tests to verify they still fail**

Run: `pytest tests/test_spiders/test_pci.py -v`
Expected: `ModuleNotFoundError`

**Step 3: Commit**

```
test: add detail parser tests for PCI Concursos spider
```

---

### Task 3: Implement spider — listing parser

**Files:**
- Create: `src/vagas/spiders/pci.py`

**Step 1: Create the spider with parse_listing**

```python
import asyncio
import json
import logging
import random
import re
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.models import Vaga

log = logging.getLogger(__name__)

BASE_URL = "https://www.pciconcursos.com.br"

# Extract slug from noticias URL: /noticias/some-slug -> some-slug
_SLUG_RE = re.compile(r"/noticias/([a-z0-9][a-z0-9-]+[a-z0-9])$", re.IGNORECASE)

# Extract salary: "até R$ 5.286,42" — works with or without vacancy count prefix
_SALARY_RE = re.compile(r"até R\$\s*([\d.,]+)")

# Extract city + state from headline: "... de Machado - MG abre ..."
# Uses the last "de {city}" before "- UF" to handle compound org names.
_LOCATION_RE = re.compile(r"\bde\s+(.+?)\s*[-–]\s*([A-Z]{2})\b")

# Detect medical positions in article body (handles plural: Médicos/Médicas)
_MEDICAL_RE = re.compile(r"\bm[ée]dic[oa]?s?\b", re.IGNORECASE)
# Exclude veterinary matches
_VETERINARY_RE = re.compile(r"\bveterin[aá]ri[oa]?s?\b", re.IGNORECASE)


class PCISpider(BaseSpider):
    """Spider para PCI Concursos (pciconcursos.com.br).

    Crawls public concursos/processos seletivos for medical positions.
    httpx-only (static HTML, no anti-bot).
    """

    name = "pci"

    _SEARCH_SLUGS = [
        "medico",
        "medico-clinico-geral",
        "medico-clinico",
        "medico-psf",
        "medico-esf",
        "medico-pediatra",
        "medico-psiquiatra",
        "medico-cardiologista",
        "medico-do-trabalho",
        "medico-ginecologista",
        "medico-ginecologista-obstetra",
        "medico-cirurgiao-geral",
        "medico-neurologista",
        "medico-oftalmologista",
        "medico-dermatologista",
        "medico-urologista",
        "medico-endocrinologista",
        "medico-ortopedista",
        "medico-plantonista",
        "medico-geriatra",
        "medico-gastroenterologista",
        "medico-nefrologista",
        "medico-reumatologista",
        "medico-especialista",
        "medico-generalista",
    ]

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    def parse_listing(self, html: str) -> list[Vaga]:
        """Extract concurso cards from a listing page."""
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []
        seen: set[str] = set()

        # da = highlighted, na = normal/recent, ea = older entries
        for card in soup.select("div.da, div.na, div.ea"):
            link = card.select_one("div.ca a")
            if not link:
                continue

            href = link.get("href", "")
            m = _SLUG_RE.search(href)
            if not m:
                continue

            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)

            company = link.get_text(strip=True)
            title = link.get("title", company)

            state_el = card.select_one("div.cc")
            state = state_el.get_text(strip=True) if state_el else None

            salary = None
            salary_max = None
            cd_el = card.select_one("div.cd")
            if cd_el:
                cd_text = cd_el.get_text(separator=" ", strip=True)
                m_sal = _SALARY_RE.search(cd_text)
                if m_sal:
                    raw = m_sal.group(1)
                    salary = f"até R$ {raw}"
                    try:
                        salary_max = float(raw.replace(".", "").replace(",", "."))
                    except ValueError:
                        pass

            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            vagas.append(Vaga(
                title=title,
                location=state or "Brasil",
                source=self.name,
                url=url,
                company=company,
                salary=salary,
                salary_max=salary_max,
                salary_period="MONTHLY",
                external_id=slug,
            ))

        return vagas
```

**Step 2: Run listing tests**

Run: `pytest tests/test_spiders/test_pci.py -k "listing" -v`
Expected: 5 PASSED

**Step 3: Commit**

```
feat(pci): add listing parser for PCI Concursos spider
```

---

### Task 4: Implement spider — detail parser

**Files:**
- Modify: `src/vagas/spiders/pci.py`

**Step 1: Add parse_detail and _parse_iso_date**

Append after `parse_listing`:

```python
    @staticmethod
    def parse_detail(html: str, vaga: Vaga) -> bool:
        """Enrich a Vaga in-place from a PCI detail page.

        Returns True if human-doctor positions were found, False otherwise.
        IMPORTANT: Only sets vaga.description when returning True — the
        crawl method's post-filter relies on description being None for
        non-medical vagas.
        """
        vaga.raw_html = html
        soup = BeautifulSoup(html, "lxml")

        # --- JSON-LD: datePublished ---
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            if not ld_tag.string:
                continue
            try:
                data = json.loads(ld_tag.string)
            except json.JSONDecodeError:
                continue

            articles = []
            if isinstance(data, dict) and "@graph" in data:
                articles = [
                    n for n in data["@graph"]
                    if isinstance(n, dict) and n.get("@type") == "NewsArticle"
                ]
            elif isinstance(data, dict) and data.get("@type") == "NewsArticle":
                articles = [data]

            if articles:
                date_str = articles[0].get("datePublished")
                if date_str:
                    vaga.published_at = _parse_iso_date(date_str)
                break

        # --- Headline -> city, state ---
        h1 = soup.select_one("h1[itemprop='headline']")
        if h1:
            loc_m = _LOCATION_RE.search(h1.get_text(strip=True))
            if loc_m:
                vaga.location = f"{loc_m.group(1).strip()}, {loc_m.group(2).strip()}"

        # --- Fallback date from abbr.published ---
        if not vaga.published_at:
            abbr = soup.select_one("abbr.published[title]")
            if abbr:
                vaga.published_at = _parse_iso_date(abbr.get("title", ""))

        # --- Article body: detect medical positions ---
        body = soup.select_one("div[itemprop='articleBody']")
        if not body:
            return False

        has_medical = False
        for el in body.select("li, p"):
            text = el.get_text(strip=True)
            if _MEDICAL_RE.search(text) and not _VETERINARY_RE.search(text):
                has_medical = True
                break

        if not has_medical:
            return False

        # Only set description for medical vagas (filter depends on this)
        vaga.description = body.get_text(separator="\n", strip=True) or None
        return True


def _parse_iso_date(s: str) -> datetime | None:
    """Parse ISO date like '2026-01-12T19:12:56-03:00'."""
    s = s.strip()
    # Remove colon in timezone offset: -03:00 -> -0300
    s = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", s)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None
```

**Step 2: Run all tests**

Run: `pytest tests/test_spiders/test_pci.py -v`
Expected: All 13 tests PASSED

**Step 3: Commit**

```
feat(pci): add detail parser with JSON-LD date and medical detection
```

---

### Task 5: Implement spider — crawl method

**Files:**
- Modify: `src/vagas/spiders/pci.py`

**Step 1: Add crawl method inside PCISpider, before parse_listing**

```python
    async def crawl(
        self,
        known_ids: set[str] | None = None,
        locations: list[str] | None = None,
    ) -> list[Vaga]:
        seen_slugs: set[str] = set()
        all_vagas: list[Vaga] = []

        async with httpx.AsyncClient(
            headers=self._HEADERS,
            follow_redirects=True,
            timeout=15.0,
            proxy=self._proxy,
        ) as client:
            # Phase 1: listing pages
            for slug in self._SEARCH_SLUGS:
                url = f"{BASE_URL}/vagas/{slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        self._record_failure()
                        log.warning("[%s] listing %s -> %d", self.name, slug, resp.status_code)
                        continue
                    self._record_success()
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] listing %s failed: %s", self.name, slug, e)
                    continue

                vagas = self.parse_listing(resp.text)
                new = 0
                for v in vagas:
                    if v.external_id and v.external_id not in seen_slugs:
                        seen_slugs.add(v.external_id)
                        all_vagas.append(v)
                        new += 1

                log.info("[%s] slug '%s': %d results (%d new)", self.name, slug, len(vagas), new)
                await asyncio.sleep(1 + random.uniform(0.5, 1.5))

            log.info("[%s] total unique from listings: %d", self.name, len(all_vagas))

            # Phase 2: detail pages (skip known_ids)
            _known = known_ids or set()
            need_detail = [v for v in all_vagas if v.external_id not in _known]
            log.info(
                "[%s] %d vagas need detail (%d already known)",
                self.name, len(need_detail), len(all_vagas) - len(need_detail),
            )

            fetched = 0
            discarded = 0
            for vaga in need_detail:
                try:
                    resp = await client.get(vaga.url)
                    if resp.status_code == 200:
                        if self.parse_detail(resp.text, vaga):
                            fetched += 1
                            self._record_success()
                        else:
                            discarded += 1
                    else:
                        self._record_failure()
                        log.warning("[%s] detail %s -> %d", self.name, vaga.url, resp.status_code)
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] detail failed %s: %s", self.name, vaga.url, e)

                await asyncio.sleep(1.5 + random.uniform(0.5, 1.5))

        # Remove vagas where detail had no medical positions.
        # parse_detail only sets description when returning True,
        # so description=None means non-medical or unfetched.
        # Known vagas (already in DB) are kept as-is.
        all_vagas = [
            v for v in all_vagas
            if v.external_id in _known or v.description is not None
        ]

        log.info("[%s] details: %d fetched, %d discarded (non-medical)", self.name, fetched, discarded)
        log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
        return all_vagas
```

**Step 2: Run all tests**

Run: `pytest tests/test_spiders/test_pci.py -v`
Expected: All 13 tests PASSED

**Step 3: Commit**

```
feat(pci): add crawl method with two-phase listing+detail fetch
```

---

### Task 6: Register spider and dry-run

**Files:**
- Modify: `src/vagas/cli.py:13-17`

**Step 1: Add import and register**

After line 13 (`from vagas.spiders.vagas_com import VagasComSpider`), add:
```python
from vagas.spiders.pci import PCISpider
```

Change line 17 from:
```python
ALL_SPIDERS = [IndeedSpider, VagasComSpider, BNESpider, InfoJobsSpider]
```
to:
```python
ALL_SPIDERS = [IndeedSpider, VagasComSpider, BNESpider, InfoJobsSpider, PCISpider]
```

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASSED

**Step 3: Dry-run against live site**

Run: `vagas pci --dry-run`

Verify:
- Listings come from interior cities across multiple states (not just SP/RJ)
- Companies are prefeituras/fundações (government orgs)
- Locations have city+state format (e.g. "Machado, MG")
- No duplicates in output
- published_at dates are present
- Descriptions contain concurso details
- No "Médico Veterinário"-only postings leak through

**Step 4: Commit**

```
feat(pci): register PCI Concursos spider in CLI
```
