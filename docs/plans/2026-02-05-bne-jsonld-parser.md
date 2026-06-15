# BNE JSON-LD Parser + Reparse Existing Data

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve BNE detail page parsing by extracting structured data from JSON-LD (`schema.org/JobPosting`), clean up HTML description by cutting UI junk, and backfill 61 existing vagas from stored `raw_html`.

**Architecture:** Replace `parse_detail` with a two-phase approach: (1) extract JSON-LD for `company` and `published_at`; (2) parse HTML for `description` (more complete than JSON-LD), `salary`, `modalidade`, `contrato`, cutting at the `Candidatar-me` marker to avoid UI junk. Add a `--reparse` CLI command (BNE-only) that re-runs `parse_detail` on vagas that have `raw_html` in the database.

**Tech Stack:** Python `json` module for JSON-LD, existing `BeautifulSoup` for HTML. No new dependencies.

---

### Context from investigation

- BNE API (`listVagas`) returns minimal data: only `Title`, `City`, `State`, `UrlJob`, `Idf_Vaga`, `Area`. No company, description, or salary.
- Detail page HTML contains a `<script type="application/ld+json">` block with `schema.org/JobPosting`. Present in 61/61 stored HTMLs (100%).
- JSON-LD `identifier.value` contains the vaga URL with `external_id` — validated correct in 61/61 cases.
- JSON-LD fields available at 100%: `hiringOrganization.name`, `description`, `datePosted`, `employmentType`, `baseSalary`, `jobLocation`.
- JSON-LD `description` is **truncated** in 85% of cases — HTML parsing gives fuller text.
- JSON-LD `baseSalary` contains **placeholder values** (45/61 have min=1000, max=15000) — not usable.
- JSON-LD `responsibilities` is present in 78% of cases — subset of `description`.
- HTML description after "Descrição Geral" contains UI junk at the end: "Candidatar-me", "Compartilhe:", "Copiado", "Plano VIP" promo — present in 100% of cases.
- Cutting description at `Candidatar-me` produces clean text in all sampled cases.
- Current DB state: 171 BNE vagas, 61 have `raw_html`, 110 don't (blocked during fetch). This plan fixes the 61. The 110 need anti-blocking improvements (separate plan).

---

### Task 1: Add JSON-LD extraction helper + tests

**Files:**
- Modify: `src/vagas/spiders/bne.py` (add `_extract_jsonld` static method)
- Create: `tests/fixtures/bne_detail.html` (fixture from real data)
- Modify: `tests/test_spiders/test_bne.py`

**Step 1: Create a realistic BNE detail page fixture**

Save a minimal but realistic HTML fixture that contains both the JSON-LD block and the HTML body structure. Use this template (based on real data from the DB):

```html
<html>
<head>
<script type="application/ld+json">
{
  "@context": "http://schema.org",
  "@type": "JobPosting",
  "employmentType": "FULL_TIME",
  "identifier": {
    "@type": "PropertyValue",
    "name": "BNE",
    "value": "https://www.bne.com.br/vaga/99999"
  },
  "title": "Médico do Trabalho",
  "description": "<p> Empresa localizada na cidade de Curitiba/PR do ramo Saude, contrata Médico do Trabalho. Atribuições: Realizar exames admissionais e periodicos </p>",
  "responsibilities": "Realizar exames admissionais e periodicos",
  "datePosted": "2026-01-20",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Hospital Santa Casa",
    "logo": "https://api-empresa.bne.com.br/api/v1/Empresa/logo/render/idFilial/158198"
  },
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Curitiba",
      "addressRegion": "PR",
      "addressCountry": "BR",
      "postalCode": "80000000",
      "streetAddress": "Curitiba,PR,"
    }
  },
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "BRL",
    "value": {
      "@type": "QuantitativeValue",
      "minValue": 1000.0,
      "maxValue": 15000.0,
      "unitText": "MONTH"
    }
  },
  "validThrough": "2036-01-20"
}
</script>
</head>
<body>
<main>
<h1>Médico do Trabalho</h1>
<p>Empresa: Hospital Santa Casa</p>
<p>Salário: R$ 12.000</p>
<p>Modalidade: Presencial</p>
<p>Contrato: Efetivo</p>
<h2>Descrição Geral</h2>
<p>Empresa localizada na cidade de Curitiba/PR do ramo Saúde, contrata Médico do Trabalho.</p>
<p>Atribuições</p>
<p>Realizar exames admissionais e periódicos. Elaborar PCMSO. Coordenar equipe de saúde ocupacional.</p>
<p>Requisitos: CRM ativo, especialização em medicina do trabalho.</p>
<p>Benefícios: Vale transporte, plano de saúde.</p>
<div>
<button>Candidatar-me</button>
</div>
<div>Compartilhe:</div>
<div>Copiado</div>
<div>Esta vaga apareceu em...</div>
<div>O que eu ganho assinando o Plano VIP?</div>
<ul><li>Candidaturas ilimitadas;</li></ul>
</main>
</body>
</html>
```

Save to: `tests/fixtures/bne_detail.html`

**Step 2: Write failing tests for JSON-LD extraction**

Add to `tests/test_spiders/test_bne.py`:

```python
def test_extract_jsonld_returns_parsed_dict():
    html = (FIXTURES / "bne_detail.html").read_text()
    data = BNESpider._extract_jsonld(html)
    assert data is not None
    assert data["@type"] == "JobPosting"
    assert data["hiringOrganization"]["name"] == "Hospital Santa Casa"


def test_extract_jsonld_returns_none_without_script():
    data = BNESpider._extract_jsonld("<html><body>no json-ld</body></html>")
    assert data is None


def test_extract_jsonld_returns_none_on_bad_json():
    html = '<html><script type="application/ld+json">{ bad json</script></html>'
    data = BNESpider._extract_jsonld(html)
    assert data is None


def test_extract_jsonld_skips_non_jobposting_blocks():
    """When multiple JSON-LD blocks exist, only JobPosting is returned."""
    html = """<html><head>
    <script type="application/ld+json">{"@type": "BreadcrumbList", "name": "nav"}</script>
    <script type="application/ld+json">{"@type": "JobPosting", "hiringOrganization": {"name": "TestCo"}}</script>
    </head></html>"""
    data = BNESpider._extract_jsonld(html)
    assert data is not None
    assert data["@type"] == "JobPosting"
    assert data["hiringOrganization"]["name"] == "TestCo"
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/test_spiders/test_bne.py -k "jsonld" -v`
Expected: FAIL — `BNESpider` has no `_extract_jsonld` method.

**Step 4: Implement `_extract_jsonld`**

Add to `BNESpider` in `src/vagas/spiders/bne.py`, before `parse_detail`.
Uses BeautifulSoup (same pattern as InfoJobs spider at `src/vagas/spiders/infojobs.py:172-182`)
to handle multiple JSON-LD blocks (e.g. BreadcrumbList + JobPosting):

```python
import json  # add to top-level imports

@staticmethod
def _extract_jsonld(html: str) -> dict | None:
    """Extract schema.org/JobPosting JSON-LD from HTML, or None."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", type="application/ld+json"):
        if not tag.string:
            continue
        try:
            data = json.loads(tag.string)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_spiders/test_bne.py -k "jsonld" -v`
Expected: 4 PASS

**Step 6: Commit**

```
feat(bne): add JSON-LD extraction helper for detail pages
```

---

### Task 2: Rewrite `parse_detail` to use JSON-LD + clean HTML description

**Files:**
- Modify: `src/vagas/spiders/bne.py` (`parse_detail` method)
- Modify: `tests/test_spiders/test_bne.py`

**Step 1: Write failing tests for new parse_detail behavior**

Add to `tests/test_spiders/test_bne.py`:

```python
def test_parse_detail_extracts_company_from_jsonld():
    """JSON-LD hiringOrganization.name is preferred for company."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.company == "Hospital Santa Casa"


def test_parse_detail_extracts_published_at_from_jsonld():
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 20


def test_parse_detail_description_excludes_ui_junk():
    """Description should NOT contain 'Candidatar-me', 'Compartilhe', 'Plano VIP'."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.description is not None
    assert "Candidatar-me" not in vaga.description
    assert "Compartilhe" not in vaga.description
    assert "Plano VIP" not in vaga.description
    assert "Candidaturas ilimitadas" not in vaga.description


def test_parse_detail_description_has_real_content():
    """Description should contain the actual job content."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert "exames admissionais" in vaga.description
    assert "PCMSO" in vaga.description


def test_parse_detail_falls_back_to_html_without_jsonld():
    """Without JSON-LD, parse_detail still works from HTML."""
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert vaga.company == "Hospital ABC"
    assert "cardiologista" in vaga.description
```

**Step 2: Run new + existing tests to see what fails**

Run: `pytest tests/test_spiders/test_bne.py -v`
Expected: new tests fail (current parse_detail includes UI junk in description, doesn't extract `published_at`). Existing tests should still pass.

**Step 3: Rewrite `parse_detail`**

Replace the `parse_detail` method in `src/vagas/spiders/bne.py`:

Add module-level constant to `src/vagas/spiders/bne.py` (outside the class, near the other constants like `MAX_PAGES`):

```python
# UI markers that appear after the real description content on detail pages
_DESC_CUT_MARKERS = ("Candidatar-me", "Compartilhe", "Copiado")
```

Then replace `parse_detail` in `BNESpider`:

```python
@staticmethod
def parse_detail(html: str, vaga: Vaga) -> None:
    """Enrich a Vaga in-place from the BNE detail page.

    Strategy:
    1. JSON-LD (schema.org/JobPosting) for company and published_at.
    2. HTML <main> text for description, salary, job_type — cutting
       at UI markers to avoid junk.
    """
    vaga.raw_html = html

    # --- Phase 1: JSON-LD -------------------------------------------
    jsonld = BNESpider._extract_jsonld(html)
    if jsonld:
        org = jsonld.get("hiringOrganization", {}).get("name", "")
        if org and org.lower() not in ("confidencial",):
            vaga.company = org

        date_str = jsonld.get("datePosted")
        if date_str:
            try:
                vaga.published_at = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                pass

    # --- Phase 2: HTML parsing --------------------------------------
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("main")
    if not main:
        log.debug("[bne] no <main> tag for %s", vaga.url)
        return

    text = main.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for i, line in enumerate(lines):
        low = line.lower()
        next_val = lines[i + 1] if i + 1 < len(lines) else ""

        # Company from HTML (fallback if JSON-LD didn't set it)
        if not vaga.company and low.startswith("empresa:"):
            val = line.split(":", 1)[1].strip() or next_val
            if val and val.lower() not in ("confidencial", "a combinar"):
                vaga.company = val

        elif low.startswith("salário:") or low.startswith("salario:"):
            val = line.split(":", 1)[1].strip() or next_val
            if val and val.lower() != "a combinar":
                vaga.salary = val

        elif low.startswith("modalidade:"):
            val = line.split(":", 1)[1].strip() or next_val
            if val:
                vaga.job_type = f"{vaga.job_type}, {val}" if vaga.job_type else val

        elif low.startswith("contrato:"):
            val = line.split(":", 1)[1].strip() or next_val
            if val:
                vaga.job_type = f"{vaga.job_type}, {val}" if vaga.job_type else val

    # Description: everything after "Descrição Geral", cut at UI markers
    desc_marker = re.search(r"descri[çc][ãa]o\s+geral", text, re.IGNORECASE)
    if desc_marker:
        desc_text = text[desc_marker.end():].strip()
        # Cut at the first UI marker
        for marker in _DESC_CUT_MARKERS:
            pos = desc_text.find(marker)
            if pos >= 0:
                desc_text = desc_text[:pos]
                break
        desc_text = re.sub(r"\n{3,}", "\n\n", desc_text).strip()
        if desc_text and desc_text.lower() != "sine":
            vaga.description = desc_text
```

**Step 4: Run all BNE tests**

Run: `pytest tests/test_spiders/test_bne.py -v`
Expected: all tests PASS (new and existing).

**Step 5: Commit**

```
feat(bne): use JSON-LD for company/date, cut UI junk from description
```

---

### Task 3: Add `--reparse` CLI command to backfill existing vagas

**Files:**
- Modify: `src/vagas/cli.py` (add `reparse_vagas` function and CLI arg)
- Modify: `src/vagas/storage.py` (add `load_vagas_with_html` function)

**Step 1: Add `load_vagas_with_html` to storage**

This function loads vagas that have `raw_html` so they can be reparsed. Add to `src/vagas/storage.py`:

```python
def load_vagas_with_html(
    conn: psycopg.Connection,
    source: str | None = None,
) -> list[tuple[Vaga, str]]:
    """Load vagas that have raw_html stored, returning (vaga, html) pairs."""
    clauses = ["raw_html IS NOT NULL"]
    params: dict = {}
    if source:
        clauses.append("source = %(source)s")
        params["source"] = source

    where = f"WHERE {' AND '.join(clauses)}"
    sql = f"""
        SELECT external_id, source, title, location, company,
               salary, salary_min, salary_max, salary_period,
               job_type, specialty, city, state,
               description, url, published_at, raw_html
        FROM vagas {where}
        ORDER BY id
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    for r in rows:
        vaga = Vaga(
            external_id=r["external_id"],
            source=r["source"],
            title=r["title"],
            location=r["location"],
            url=r["url"],
        )
        results.append((vaga, r["raw_html"]))
    return results
```

Note: we create fresh `Vaga` objects with only the immutable fields (external_id, source, title, location, url) — `parse_detail` will fill in the rest from the HTML. This way we re-extract everything cleanly rather than merging with stale data.

**Step 2: Add `reparse_vagas` function to cli.py**

Add to `src/vagas/cli.py`:

```python
def reparse_vagas():
    """Re-run BNE parse_detail on vagas that have stored raw_html."""
    from vagas.spiders.bne import BNESpider
    from vagas.storage import load_vagas_with_html

    conn = get_connection()
    ensure_table(conn)

    # Only BNE has parse_detail; hardcode source to avoid misuse
    pairs = load_vagas_with_html(conn, source="bne")
    log.info("Loaded %d BNE vagas with raw_html to reparse", len(pairs))

    if not pairs:
        conn.close()
        return

    spider = BNESpider()
    reparsed = []
    for vaga, html in pairs:
        spider.parse_detail(html, vaga)
        vaga.specialty = normalize_specialty(vaga.specialty)
        vaga.city, vaga.state = normalize_location(vaga.location)
        reparsed.append(vaga)

    version = crawler_version(spider)
    ins, upd = upsert_vagas(conn, reparsed, version)
    log.info("Reparse done: %d inserted, %d updated, %d unchanged",
             ins, upd, len(reparsed) - ins - upd)
    conn.close()
```

**Step 3: Wire `--reparse` into argparse**

In `cli.py`'s `main()`, add the argument and handler:

```python
# In argparse setup:
parser.add_argument("--reparse", action="store_true",
                    help="Re-parse BNE vagas from stored raw_html (improves extraction)")

# In handler chain (before the else clause):
elif args.reparse:
    reparse_vagas()
```

**Step 4: Run all tests to verify nothing broke**

Run: `pytest tests/ -v`
Expected: all PASS.

**Step 5: Commit**

```
feat(cli): add --reparse command to backfill vagas from stored HTML
```

---

### Task 4: Run reparse and verify improvement

**Step 1: Check current state**

Run:
```bash
vagas --stats
```

Note the "Dados faltantes" numbers for Empresa and Descrição.

**Step 2: Run reparse**

Run:
```bash
vagas --reparse
```

Expected output: `Reparse done: 0 inserted, ~61 updated, 0 unchanged` (or similar — the COALESCE upsert means new data fills NULLs).

**Step 3: Verify improvement**

Run:
```bash
vagas --stats
```

Compare "Dados faltantes" — the "Empresa" and "Descrição" counts should both decrease (the 61 vagas with `raw_html` should now have company and clean descriptions).

**Step 4: Spot-check a few vagas**

Quick SQL to verify the previously-problematic vaga 5721827:

```bash
psql $DATABASE_URL -c "SELECT company, LEFT(description, 200) FROM vagas WHERE external_id = '5721827' AND source = 'bne';"
```

Expected: `company = 'Cuiaba Esporte Clube'`, description without "Candidatar-me" junk.

**Step 5: Commit**

No code changes, but if stats look good:

```
chore: run --reparse to backfill BNE vagas from stored HTML
```

This is a no-op commit to mark the milestone. Skip if you prefer.
