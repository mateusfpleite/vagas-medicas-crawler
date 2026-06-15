# Medical Scoring Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a scoring module that assigns a 0.0–1.0 probability score to each vaga, filtering non-doctor jobs that slip past the existing regex+blocklist filters.

**Architecture:** A pure function `medical_score(title, description)` in `src/vagas/scoring.py` that accumulates positive/negative signals from title and description text. Integrated at two pipeline points: pre-detail (title only, inside each spider's parse method) and post-detail (title + description, centralized in `cli.py`).

**Tech Stack:** Python stdlib only (re module). No external dependencies.

---

### Task 1: Core scoring function — title signals

**Files:**
- Create: `src/vagas/scoring.py`
- Create: `tests/test_scoring.py`

**Context:** The scoring module lives alongside `filters.py` and `normalize.py` in `src/vagas/`. It uses `strip_accents` from `src/vagas/utils.py` for accent-insensitive matching. The known specialties list should reuse the keys from `src/vagas/normalize.py`'s `_SPECIALTY_MAP` (values, deduplicated) plus the canonical list from `src/vagas/enrich.py`'s `CANONICAL_SPECIALTIES`.

**Step 1: Write the failing tests**

Create `tests/test_scoring.py`:

```python
import pytest

from vagas.scoring import medical_score, TITLE_THRESHOLD


class TestTitleScoring:
    """Title-only scoring (pre-detail filter)."""

    @pytest.mark.parametrize("title", [
        "Médico Cardiologista",
        "Médica Pediatra",
        "MÉDICO PLANTONISTA",
        "Médico(a) do Trabalho",
        "Médico Clínico Geral",
        "Médico Ginecologista - APS Santa Marcelina",
        "Médico Cirurgião",
        "Médico Oftalmologista",
        "Médico Endocrinologista",
        "Médica Endocrinologista",
        "Médico do Trabalho RQE",
        "Médico do Trabalho Especialista",
        "Médico do Trabalho Coordenador Nacional com RQE",
        "Médico Psiquiatra",
        "Médico",
    ])
    def test_doctor_titles_score_high(self, title):
        score = medical_score(title)
        assert score >= TITLE_THRESHOLD, (
            f"medical_score({title!r}) = {score}, expected >= {TITLE_THRESHOLD}"
        )

    @pytest.mark.parametrize("title", [
        # "Clínica Médica" as adjective of workplace
        "Consultor Comercial - Clínica Médica Dermatológica",
        "Closer - Clínica Médica Estética",
        "Líder Atendimento Clínica Médica",
        "Secretária Clínica Médica",
        "Supervisora Clínica Médica",
        "Recepcionista Clínica Médica Dermatologia",
        "Secretária Clínica Médica Secretária",
        "Consultor Comercial Clínica Médica",
        # Pharma rep / corporate
        "PROPAGANDISTA MÉDICO JUNIOR",
        "Assessor(a) Médico(a) Prova Funcional",
        # Academic
        "Professor Médico Endocrinologia",
    ])
    def test_non_doctor_titles_score_low(self, title):
        score = medical_score(title)
        assert score < TITLE_THRESHOLD, (
            f"medical_score({title!r}) = {score}, expected < {TITLE_THRESHOLD}"
        )

    def test_empty_title(self):
        assert medical_score("") == 0.0
        assert medical_score("   ") == 0.0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vagas.scoring'`

**Step 3: Implement the scoring module**

Create `src/vagas/scoring.py`:

```python
"""Probabilistic scoring for medical job listings."""

import re

from vagas.utils import strip_accents

# Thresholds
TITLE_THRESHOLD = 0.4   # pre-detail filter (permissive)
FULL_THRESHOLD = 0.5    # post-detail filter (stricter)

# --- Known specialties (for title signal) -----------------------------------

_KNOWN_SPECIALTIES = {
    "anestesista", "anestesiologista",
    "cardiologista",
    "cirurgiao", "cirurgia",
    "clinico", "clinica medica",
    "dermatologista",
    "endocrinologista",
    "fisiatra",
    "gastroenterologista",
    "geriatra",
    "ginecologista", "obstetra",
    "infectologista",
    "intensivista",
    "nefrologista",
    "neonatologista",
    "neurologista",
    "oftalmologista",
    "oncologista",
    "ortopedista",
    "otorrinolaringologista",
    "pediatra",
    "plantonista",
    "pneumologista",
    "proctologista",
    "psiquiatra",
    "radiologista", "ultrassonografista",
    "reumatologista",
    "urologista",
    "generalista",
    "emergencista", "urgentista",
    "hematologista",
}

_SPECIALTY_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in sorted(_KNOWN_SPECIALTIES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# --- Title signals -----------------------------------------------------------

# "Médico" / "Médica" as first word of title
_MEDICO_FIRST_RE = re.compile(
    r"^\s*m[ée]dic[oa]?\b", re.IGNORECASE,
)

# "Médico" / "Médica" after hyphen: "Vaga - Médico do Trabalho"
_MEDICO_AFTER_HYPHEN_RE = re.compile(
    r"[-–—]\s*m[ée]dic[oa]?\b", re.IGNORECASE,
)

# "Médico(a)" with gender flex in parentheses
_MEDICO_FLEX_RE = re.compile(
    r"m[ée]dic[oa]?\s*\([oa]\)", re.IGNORECASE,
)

# Non-doctor job titles as first word
_NON_DOCTOR_FIRST_RE = re.compile(
    r"^\s*("
    r"secret[aá]ri[oa]"
    r"|recepcionista"
    r"|consultor[a]?"
    r"|closer"
    r"|supervisor[a]?"
    r"|l[ií]der"
    r"|professor[a]?"
    r"|assessor[a]?"
    r"|coordenador[a]?"
    r"|analista"
    r"|gerente"
    r"|diretor[a]?"
    r"|assistente"
    r"|estagiári[oa]"
    r"|vendedor[a]?"
    r"|auxiliar"
    r"|atendente"
    r"|t[ée]cnic[oa]"
    r"|enfermeiro[a]?"
    r"|farmac[êe]utic[oa]"
    r"|fisioterapeuta"
    r"|nutricionista"
    r"|psic[oó]log[oa]"
    r")\b",
    re.IGNORECASE,
)

# "Clínica Médica" / "Área Médica" / "Equipe Médica" — adjective of workplace
_ADJECTIVE_MEDICA_RE = re.compile(
    r"\b(cl[ií]nica|[aá]rea|equipe|empresa|ind[uú]stria|rede|unidade)\s+m[ée]dic[oa]?\b",
    re.IGNORECASE,
)

# "Propagandista Médico" — pharma rep
_PROPAGANDISTA_RE = re.compile(
    r"\bpropagandista\s+m[ée]dic[oa]?\b", re.IGNORECASE,
)

# --- Description signals -----------------------------------------------------

_CRM_RE = re.compile(r"\bCRM\b", re.IGNORECASE)
_RQE_RE = re.compile(r"\bRQE\b", re.IGNORECASE)

_CLINICAL_PROCEDURES_RE = re.compile(
    r"\b("
    r"prescri[çc][ãa]o"
    r"|diagn[oó]stico"
    r"|laudo"
    r"|cirurgia"
    r"|consulta\s+m[ée]dica"
    r"|atendimento\s+a\s+pacientes"
    r"|prontu[aá]rio"
    r"|anamnese"
    r"|exame\s+f[ií]sico"
    r")\b",
    re.IGNORECASE,
)

_HEALTHCARE_FACILITY_RE = re.compile(
    r"\b("
    r"hospital"
    r"|UBS"
    r"|UPA"
    r"|PSF"
    r"|pronto.socorro"
    r"|ambulat[oó]rio"
    r"|consult[oó]rio"
    r"|emer[gê]ncia"
    r"|urg[eê]ncia"
    r"|UTI"
    r"|CTI"
    r")\b",
    re.IGNORECASE,
)

_PLANTAO_RE = re.compile(
    r"\bplant[ãa]o\s*\d+\s*h", re.IGNORECASE,
)

_SALES_RE = re.compile(
    r"\b(vendas|comercial|metas\s+de\s+venda|captação\s+de\s+clientes)\b",
    re.IGNORECASE,
)

_PHARMA_INDUSTRY_RE = re.compile(
    r"\b(ind[uú]stria\s+farmac[eê]utica|farmac[eê]utic[oa]s?\s+(?:ltda|s\.?a|inc))\b",
    re.IGNORECASE,
)

_VISITACAO_RE = re.compile(
    r"\b(visita[çc][ãa]o|visita\s+m[ée]dica)\b",
    re.IGNORECASE,
)

_CUSTOMER_SERVICE_RE = re.compile(
    r"\batendimento\s+ao\s+cliente\b",
    re.IGNORECASE,
)

_LOW_EDUCATION_RE = re.compile(
    r"\b(ensino\s+m[ée]dio|t[ée]cnico\s+em\b)",
    re.IGNORECASE,
)

_SALES_EXPERIENCE_RE = re.compile(
    r"\b(experi[eê]ncia\s+(?:em\s+)?vendas|experi[eê]ncia\s+comercial|negocia[çc][ãa]o)\b",
    re.IGNORECASE,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def medical_score(title: str, description: str | None = None) -> float:
    """Score a vaga from 0.0 (not doctor) to 1.0 (definitely doctor).

    With only a title, scores based on syntactic position of "médic" and
    presence of known specialties. With a description, adds clinical and
    commercial signals.
    """
    if not title or not title.strip():
        return 0.0

    normalized_title = strip_accents(title)
    score = 0.5

    # --- Title signals ---

    if _MEDICO_FIRST_RE.search(normalized_title):
        score += 0.4
    elif _MEDICO_AFTER_HYPHEN_RE.search(normalized_title):
        score += 0.3
    elif _ADJECTIVE_MEDICA_RE.search(normalized_title):
        score -= 0.3
    else:
        # "médico" present but not in strong position
        if re.search(r"\bm[ée]dic[oa]?\b", normalized_title, re.IGNORECASE):
            score -= 0.2

    if _MEDICO_FLEX_RE.search(normalized_title):
        score += 0.2

    if _SPECIALTY_RE.search(strip_accents(title)):
        score += 0.2

    if _NON_DOCTOR_FIRST_RE.search(normalized_title):
        score -= 0.4

    if _PROPAGANDISTA_RE.search(normalized_title):
        score -= 0.3

    # --- Description signals (if available) ---

    if description:
        desc_norm = strip_accents(description)

        if _CRM_RE.search(description):
            score += 0.3
        if _RQE_RE.search(description):
            score += 0.3
        if _SPECIALTY_RE.search(desc_norm):
            score += 0.2
        if _CLINICAL_PROCEDURES_RE.search(desc_norm):
            score += 0.15
        if _HEALTHCARE_FACILITY_RE.search(desc_norm):
            score += 0.1
        if _PLANTAO_RE.search(desc_norm):
            score += 0.1
        if _SALES_RE.search(desc_norm):
            score -= 0.3
        if _PHARMA_INDUSTRY_RE.search(desc_norm):
            score -= 0.3
        if _VISITACAO_RE.search(desc_norm):
            score -= 0.2
        if _CUSTOMER_SERVICE_RE.search(desc_norm):
            score -= 0.2
        if _LOW_EDUCATION_RE.search(desc_norm):
            score -= 0.2
        if _SALES_EXPERIENCE_RE.search(desc_norm):
            score -= 0.2

    return _clamp(score)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scoring.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests still pass

---

### Task 2: Description signal tests

**Files:**
- Modify: `tests/test_scoring.py`

**Context:** Task 1 only tested title-only scoring. Now add tests for title + description combinations, which activate the description signals (CRM, RQE, clinical procedures, sales, etc.).

**Step 1: Add description signal tests**

Append to `tests/test_scoring.py`:

```python
class TestDescriptionScoring:
    """Title + description scoring (post-detail filter)."""

    def test_ambiguous_title_with_crm_scores_high(self):
        """Generic "Médico" title boosted by CRM in description."""
        score = medical_score("Médico", "Necessário CRM ativo e disponibilidade para plantão.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_rqe_scores_high(self):
        score = medical_score("Médico", "Exigido RQE em cardiologia.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_specialty_in_desc(self):
        score = medical_score("Médico", "Buscamos cardiologista para atuar em hospital.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_clinical_procedures(self):
        score = medical_score("Médico", "Atendimento a pacientes, prescrição e diagnóstico.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_healthcare_facility(self):
        score = medical_score("Médico", "Atuar no pronto-socorro do hospital municipal.")
        assert score >= FULL_THRESHOLD

    def test_ambiguous_title_with_plantao_hours(self):
        score = medical_score("Médico", "Plantão 12h diurno na UTI.")
        assert score >= FULL_THRESHOLD

    def test_sales_description_lowers_score(self):
        """Non-doctor role with sales description."""
        score = medical_score(
            "Consultor Comercial - Clínica Médica",
            "Experiência em vendas e captação de clientes. Metas de venda mensais.",
        )
        assert score < FULL_THRESHOLD

    def test_pharma_industry_lowers_score(self):
        score = medical_score(
            "PROPAGANDISTA MÉDICO JUNIOR",
            "Atuação na indústria farmacêutica. Visitação médica em consultórios.",
        )
        assert score < FULL_THRESHOLD

    def test_low_education_lowers_score(self):
        score = medical_score(
            "Auxiliar de Consultório Médico",
            "Ensino médio completo. Experiência em atendimento ao cliente.",
        )
        assert score < FULL_THRESHOLD

    def test_good_title_reinforced_by_description(self):
        """Strong title + strong description = max score."""
        score = medical_score(
            "Médico Cardiologista",
            "Necessário CRM ativo e RQE. Atendimento em consultório e hospital.",
        )
        assert score == 1.0
```

Also import `FULL_THRESHOLD` in the existing import line:

```python
from vagas.scoring import medical_score, TITLE_THRESHOLD, FULL_THRESHOLD
```

**Step 2: Run tests**

Run: `pytest tests/test_scoring.py -v`
Expected: All PASS. If any fail, adjust weights in `scoring.py` — the tests define the contract, the weights are tuned to satisfy them.

---

### Task 3: Integrate pre-detail scoring into InfoJobs spider

**Files:**
- Modify: `src/vagas/spiders/infojobs.py:12,144-148`
- Modify: `tests/test_spiders/test_infojobs.py`

**Context:** The InfoJobs spider currently filters with regex allowlist + `is_medical_title()` blocklist in `parse_listing()`. Add `medical_score(title) >= TITLE_THRESHOLD` as a third filter layer. This is where most false positives were found.

**Step 1: Update the test to expect scoring filter**

In `tests/test_spiders/test_infojobs.py`, update `test_parse_listing_filters_non_medical` to add a case that passes the existing filters but fails scoring:

```python
def test_parse_listing_filters_non_medical():
    """Three-layer filter: allowlist (must contain 'médic') + blocklist + scoring."""
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico-geral__1.aspx"><h2>Médico Clínico Geral</h2></a>
    <a href="/vaga-de-balconista__2.aspx"><h2>Balconista De Medicamentos</h2></a>
    <a href="/vaga-de-veterinario__3.aspx"><h2>Médico Veterinário</h2></a>
    <a href="/vaga-de-enfermeiro__4.aspx"><h2>Enfermeiro Intensivista</h2></a>
    <a href="/vaga-de-psiquiatra__5.aspx"><h2>Médico Psiquiatra</h2></a>
    <a href="/vaga-de-docente__6.aspx"><h2>Docente Medicina Veterinária</h2></a>
    <a href="/vaga-de-auxiliar__7.aspx"><h2>Auxiliar de Consultório Médico</h2></a>
    <a href="/vaga-de-secretaria__8.aspx"><h2>Secretária Clínica Médica</h2></a>
    <a href="/vaga-de-closer__9.aspx"><h2>Closer - Clínica Médica Estética</h2></a>
    <a href="/vaga-de-propagandista__10.aspx"><h2>PROPAGANDISTA MÉDICO JUNIOR</h2></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    titles = {v.title for v in vagas}
    assert "Médico Clínico Geral" in titles
    assert "Médico Psiquiatra" in titles
    # Existing filters catch these:
    assert "Balconista De Medicamentos" not in titles
    assert "Enfermeiro Intensivista" not in titles
    assert "Docente Medicina Veterinária" not in titles
    assert "Médico Veterinário" not in titles
    assert "Auxiliar de Consultório Médico" not in titles
    # NEW: scoring catches these (pass regex+blocklist but fail score):
    assert "Secretária Clínica Médica" not in titles
    assert "Closer - Clínica Médica Estética" not in titles
    assert "PROPAGANDISTA MÉDICO JUNIOR" not in titles
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spiders/test_infojobs.py::test_parse_listing_filters_non_medical -v`
Expected: FAIL — "Secretária Clínica Médica" is still in titles.

**Step 3: Add scoring to InfoJobs parse_listing**

In `src/vagas/spiders/infojobs.py`, add import at top:

```python
from vagas.scoring import medical_score, TITLE_THRESHOLD
```

In `parse_listing()`, after the existing two filters (lines ~145-148), add the scoring filter:

```python
            # Two-layer filter: allowlist + blocklist (avoid detail fetches for non-doctors)
            if not _TITLE_MEDICAL_RE.search(title):
                continue
            if not is_medical_title(title):
                continue
            if medical_score(title) < TITLE_THRESHOLD:
                continue
```

**Step 4: Run tests**

Run: `pytest tests/test_spiders/test_infojobs.py -v`
Expected: All 9 PASS

**Step 5: Run full suite**

Run: `pytest tests/ -v`
Expected: All pass

---

### Task 4: Integrate pre-detail scoring into VagasCom spider

**Files:**
- Modify: `src/vagas/spiders/vagas_com.py:9,66-70`
- Modify: `tests/test_spiders/test_vagas_com.py`

**Context:** VagasCom currently filters with `_TITLE_MEDICAL_RE` + `_TITLE_EXCLUDE_RE` in `parse()` (lines 67-70). Add scoring as third layer.

**Step 1: Update test**

In `tests/test_spiders/test_vagas_com.py`, find the `test_parse_filters_non_medical` test. Add a case that passes existing filters but fails scoring. The VagasCom test fixtures use `li.vaga` cards — check the existing test structure and add a card with title "Secretária Clínica Médica" (contains "médic", not in exclude list, but should fail scoring):

```python
def test_parse_filters_scoring():
    """Scoring filter catches titles that pass regex+blocklist."""
    spider = VagasComSpider()
    html = """<html><body><ul>
    <li class="vaga">
      <span class="cargo"><a href="/v123" data-id-vaga="123">Secretária Clínica Médica</a></span>
      <span class="emprVaga">Empresa X</span>
      <span class="vaga-local">São Paulo</span>
    </li>
    <li class="vaga">
      <span class="cargo"><a href="/v456" data-id-vaga="456">Médico Cardiologista</a></span>
      <span class="emprVaga">Hospital Y</span>
      <span class="vaga-local">São Paulo</span>
    </li>
    </ul></body></html>"""
    vagas = spider.parse(html)
    titles = {v.title for v in vagas}
    assert "Secretária Clínica Médica" not in titles
    assert "Médico Cardiologista" in titles
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spiders/test_vagas_com.py::test_parse_filters_scoring -v`
Expected: FAIL

**Step 3: Add scoring to VagasCom parse**

In `src/vagas/spiders/vagas_com.py`, add import:

```python
from vagas.scoring import medical_score, TITLE_THRESHOLD
```

After the existing filters in `parse()` (around line 70), add:

```python
            if not _TITLE_MEDICAL_RE.search(title):
                continue
            if _TITLE_EXCLUDE_RE.search(title):
                continue
            if medical_score(title) < TITLE_THRESHOLD:
                continue
```

**Step 4: Run tests**

Run: `pytest tests/test_spiders/test_vagas_com.py -v`
Expected: All PASS

---

### Task 5: Integrate pre-detail scoring into Indeed spider

**Files:**
- Modify: `src/vagas/spiders/indeed.py:11,132-134`
- Modify: `tests/test_spiders/test_indeed.py`

**Context:** Indeed uses `_is_medical_norm(normTitle)` + `_TITLE_EXCLUDE_RE.search(title)` to filter in `parse_mosaic()`. The normTitle filter is strong (Indeed provides structured data), so scoring here is defense-in-depth — unlikely to trigger in production, but prevents edge cases if Indeed's classification is wrong. Add scoring after existing filters.

**Step 1: Add a test case**

In `tests/test_spiders/test_indeed.py`, add a test that provides a mosaic result with normTitle="medico" (passes `_is_medical_norm`) but title="Coordenador Médico de Área" (a more realistic false positive — Indeed could classify area coordinators as "medico"). Check the existing test structure for `parse_mosaic` and follow the same pattern. Add a comment noting this is defense-in-depth.

**Step 2: Run test to verify it fails**

**Step 3: Add scoring**

In `src/vagas/spiders/indeed.py`, add import:

```python
from vagas.scoring import medical_score, TITLE_THRESHOLD
```

After the existing filters in `parse_mosaic()` (after `_TITLE_EXCLUDE_RE` check, around line 134), add:

```python
            if medical_score(title) < TITLE_THRESHOLD:
                continue
```

**Step 4: Run tests**

Run: `pytest tests/test_spiders/test_indeed.py -v`
Expected: All PASS

---

### Task 6: Integrate pre-detail scoring into BNE spider

**Files:**
- Modify: `src/vagas/spiders/bne.py:11,72-73`
- Modify: `tests/test_spiders/test_bne.py`

**Context:** BNE's `parse()` currently does NO filtering — it accepts all results from the API. The scoring filter is the first filter BNE will have at the parse level. Add it after title extraction (line 72) and before appending to vagas.

**Step 1: Add a test case**

In `tests/test_spiders/test_bne.py`, add a test with a BNE API response containing a non-doctor title like "Secretária Clínica Médica" alongside a real doctor title. Verify the non-doctor is filtered out.

**Step 2: Run test to verify it fails**

**Step 3: Add scoring**

In `src/vagas/spiders/bne.py`, add import:

```python
from vagas.scoring import medical_score, TITLE_THRESHOLD
```

In `parse()`, after `if not title: continue` (line 73), add:

```python
            if medical_score(title) < TITLE_THRESHOLD:
                continue
```

**Step 4: Run tests**

Run: `pytest tests/test_spiders/test_bne.py -v`
Expected: All PASS

---

### Task 7: Centralized post-detail scoring in cli.py

**Files:**
- Modify: `src/vagas/cli.py:6,51-52`

**Context:** After `crawl()` returns all vagas (with descriptions from detail pages), apply the full scoring filter centrally in `cli.py` before normalize/enrich/upsert. This catches false positives that passed the title-only pre-detail filter thanks to description signals.

**Step 1: Write a unit test for the post-detail filter logic**

Create `tests/test_scoring_integration.py`:

```python
from vagas.models import Vaga
from vagas.scoring import medical_score, FULL_THRESHOLD


def _make_vaga(title: str, description: str | None = None) -> Vaga:
    return Vaga(title=title, location="Brasil", source="test", url="http://x", description=description)


def test_post_detail_filter_removes_non_doctors():
    """Simulate the cli.py post-detail scoring filter."""
    vagas = [
        _make_vaga("Médico Cardiologista", "CRM ativo, atendimento em hospital."),
        _make_vaga("Secretária Clínica Médica", "Atendimento ao cliente, ensino médio."),
        _make_vaga("Médico do Trabalho", "RQE obrigatório, exames ocupacionais."),
        _make_vaga("PROPAGANDISTA MÉDICO", "Indústria farmacêutica, vendas."),
    ]
    filtered = [v for v in vagas if medical_score(v.title, v.description) >= FULL_THRESHOLD]
    titles = {v.title for v in filtered}
    assert "Médico Cardiologista" in titles
    assert "Médico do Trabalho" in titles
    assert "Secretária Clínica Médica" not in titles
    assert "PROPAGANDISTA MÉDICO" not in titles


def test_post_detail_filter_keeps_ambiguous_with_good_description():
    """Ambiguous title rescued by strong description signals."""
    vaga = _make_vaga("Médico", "Necessário CRM ativo. Plantão 12h na UBS.")
    assert medical_score(vaga.title, vaga.description) >= FULL_THRESHOLD
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring_integration.py -v`
Expected: FAIL with `ModuleNotFoundError` (scoring.py doesn't exist yet if running standalone — but if running after Task 1, should PASS)

**Step 3: Add import to cli.py**

```python
from vagas.scoring import medical_score, FULL_THRESHOLD
```

**Step 4: Add post-detail filter**

In `cli.py`'s `run()` function, after `vagas = await spider.crawl(known_ids=known)` and the log line (line ~52), add:

```python
            # Post-detail scoring filter (uses title + description)
            before_scoring = len(vagas)
            vagas = [
                v for v in vagas
                if medical_score(v.title, v.description) >= FULL_THRESHOLD
            ]
            if before_scoring != len(vagas):
                log.info(
                    "[%s] Scoring filter: %d -> %d vagas",
                    spider.name, before_scoring, len(vagas),
                )
```

This goes BEFORE the normalize and enrich steps.

**Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

---

### Task 8: Integration test — InfoJobs dry-run

**Files:** None (manual verification)

**Step 1: Run InfoJobs dry-run**

Run: `vagas infojobs --dry-run`

**Step 2: Verify results**

Expected:
- False positives from before (Secretária, Closer, Propagandista, etc.) should be gone
- Real doctor vagas (Médico Cardiologista, Médico do Trabalho, etc.) should remain
- Total vagas count should be lower than the 48 from the previous run
- Log should show "Scoring filter: X -> Y vagas" line

**Step 3: If false positives remain, note titles and add to test suite, adjust weights**
