# Enrichment Quality: Defense-in-Depth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix three data quality problems: non-doctor vagas not filtered, specialties missed by AI, and corrupted BNE data — using layered deterministic + AI approach.

**Architecture:** Three defense layers applied in order: (1) deterministic title pre-filter shared across all spiders, (2) expanded normalize.py with more synonym mappings, (3) improved AI enrichment that deletes non-doctor vagas from DB. Each layer catches what the previous missed.

**Tech Stack:** Python 3.12+, pytest, psycopg, Google Gemini API

---

### Task 1: Deterministic title pre-filter

Shared utility that all spiders (and `enrich_only`) can use to reject obvious non-doctor titles before any AI call.

**Files:**
- Create: `src/vagas/filters.py`
- Test: `tests/test_filters.py`

**Step 1: Write the failing tests**

```python
# tests/test_filters.py
import pytest
from vagas.filters import is_medical_title

@pytest.mark.parametrize("title,expected", [
    # Should PASS (doctor titles)
    ("Médico Cardiologista", True),
    ("MÉDICO PLANTONISTA", True),
    ("Médico", True),
    ("médico", True),
    ("Médico Offshore", True),
    ("Médico(a) do Trabalho", True),
    # Should REJECT (non-doctor)
    ("Enfermeiro Assistencial", False),
    ("Enfermeira Unidade de Internação Pediátrica", False),
    ("Fisioterapeuta (CTI Pediátrico)", False),
    ("Farmacêutico(a) RT – Clínica de Cirurgia Plástica", False),
    ("TÉCNICO DE IMOBILIZAÇÃO ORTOPÉDICA", False),
    ("Técnico de enfermagem", False),
    ("Nutricionista Clínica", False),
    ("Psicólogo Hospitalar", False),
    ("Fonoaudiólogo", False),
    ("Biomédico", False),
    ("Terapeuta Ocupacional", False),
    ("Assistente Social", False),
    ("Gestora Comercial (Clínica de Cirurgia Plástica)", False),
    ("ATENDENTE CLINICA CIRURGIA PLASTICA", False),
    ("Representante Visitação Médica", False),
    ("Promotor Médico", False),
    ("Analista Médico Científico", False),
    ("Executivo de Relacionamento Médico", False),
    ("Medico Veterinario- São Judas", False),
    ("MEDICO VETERINÁRIO", False),
    ("Balconista", False),
    ("Vendedor", False),
    ("Auxiliar de médico", False),
])
def test_is_medical_title(title, expected):
    assert is_medical_title(title) == expected, f"is_medical_title({title!r}) should be {expected}"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filters.py -v`
Expected: FAIL (module not found)

**Step 3: Implement**

```python
# src/vagas/filters.py
"""Deterministic pre-filters for medical job listings."""

import re
import unicodedata


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


# Titles that are clearly NOT doctor positions, even if "médico" appears in context
_NON_DOCTOR_RE = re.compile(
    r"\b("
    r"veterinari[oa]"
    r"|enfermeiro|enfermeira"
    r"|farmac[eê]utic[oa]"
    r"|fisioterapeuta"
    r"|nutricionista"
    r"|psic[oó]log[oa]"
    r"|biom[eé]dic[oa]"
    r"|fonoaudi[oó]log[oa]"
    r"|t[eé]cnic[oa]\b"
    r"|terapeuta\s+ocupacional"
    r"|assistente\s+social"
    r"|atendente"
    r"|balconista"
    r"|vendedor[a]?"
    r"|auxiliar"
    r"|gestor[a]?"
    r"|promotor[a]?\s+m[eé]dic[oa]"
    r"|representante\s+visita[çc][aã]o"
    r"|analista\s+m[eé]dic[oa]"
    r"|executiv[oa]\s+de\s+relacionamento"
    r")\b",
    re.IGNORECASE,
)


def is_medical_title(title: str) -> bool:
    """Return True if the title looks like a doctor vacancy.

    Uses a blocklist approach: rejects known non-doctor patterns.
    Titles without any recognizable pattern are assumed to be doctor
    vacancies (conservative — let AI handle ambiguous cases).
    """
    if not title or not title.strip():
        return False

    normalized = _strip_accents(title)

    # Check blocklist first
    if _NON_DOCTOR_RE.search(normalized):
        return False

    return True
```

**Step 4: Run tests**

Run: `pytest tests/test_filters.py -v`
Expected: PASS

**Step 5: Commit**

```
feat: add deterministic title pre-filter for non-doctor vagas
```

---

### Task 2: Expand normalize.py with missing synonyms

Add mappings for specialties the AI missed: occupational medicine synonyms, ultrassonografista, angiologista, etc.

**Files:**
- Modify: `src/vagas/normalize.py:41-95` (add entries to `_SPECIALTY_MAP`)
- Modify: `tests/test_normalize.py` (add parametrized cases)

**Step 1: Add failing test cases**

Append to the parametrize list in `tests/test_normalize.py`:

```python
    # Occupational medicine synonyms
    ("Medicina Ocupacional", "Medicina do Trabalho"),
    ("Médico Examinador Ocupacional", "Medicina do Trabalho"),
    # Radiology / imaging
    ("Ultrassonografista", "Radiologista"),
    # Angiologista -> Cirurgião Vascular
    ("Angiologista", "Cirurgião Vascular"),
    # Anestesiologista (new canonical)
    ("Anestesista", "Anestesiologista"),
    ("Anestesiologista", "Anestesiologista"),
    # Emergencista -> Clínico Geral
    ("Emergencista", "Clínico Geral"),
    ("Urgentista", "Clínico Geral"),
    # Hematologista -> Oncologista (closest canonical)
    ("Hematologista", "Oncologista"),
    # Obstetra standalone
    ("Obstetra", "Ginecologista"),
```

**Step 2: Run to verify failure**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL on new cases

**Step 3: Add mappings and new canonical specialty**

In `src/vagas/normalize.py`, add entries to `_SPECIALTY_MAP`:

```python
    # Medicina do Trabalho (synonyms)
    "medicina ocupacional": "Medicina do Trabalho",
    "medico examinador ocupacional": "Medicina do Trabalho",
    # Radiologista (synonyms)
    "ultrassonografista": "Radiologista",
    # Cirurgião Vascular (synonyms)
    "angiologista": "Cirurgião Vascular",
    # Anestesiologista
    "anestesista": "Anestesiologista",
    "anestesiologista": "Anestesiologista",
    # Clínico Geral (emergency synonyms)
    "emergencista": "Clínico Geral",
    "urgentista": "Clínico Geral",
    # Oncologista (hematology synonym)
    "hematologista": "Oncologista",
    # Ginecologista (standalone obstetra)
    "obstetra": "Ginecologista",
```

Also add `"Anestesiologista"` to `CANONICAL_SPECIALTIES` in `src/vagas/enrich.py`.

**Step 4: Run tests**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS

**Step 5: Commit**

```
feat: expand specialty normalization with occupational, radiology and anesthesiology synonyms
```

---

### Task 3: Wire pre-filter into enrich_vagas and enrich_only

Apply `is_medical_title` before sending vagas to Gemini. This reduces API calls and catches obvious non-doctors deterministically.

**Files:**
- Modify: `src/vagas/enrich.py:166-236` (enrich_vagas function)
- Modify: `tests/test_enrich.py` (add test for pre-filtering)

**Step 1: Write failing test**

Add to `tests/test_enrich.py`:

```python
def test_enrich_vagas_prefilters_non_doctor_titles():
    """Non-doctor titles should be filtered before AI call."""
    vagas = [
        _vaga(title="Farmacêutico(a) RT"),
        _vaga(title="Médico Pediatra"),
        _vaga(title="Enfermeiro Assistencial"),
    ]
    with patch("vagas.enrich.genai") as mock_genai:
        # AI only sees the 1 doctor vaga
        mock_client = _mock_client([
            {"id": 1, "specialty": "Pediatra", "is_doctor": True},
        ])
        mock_genai.Client.return_value = mock_client

        enriched, non_doc = enrich_vagas(vagas, api_key="fake-key")
        assert non_doc == 2  # farmaceutico + enfermeiro
        assert enriched == 1
        assert vagas[1].specialty == "Pediatra"
```

**Step 2: Run to verify failure**

Run: `pytest tests/test_enrich.py::test_enrich_vagas_prefilters_non_doctor_titles -v`
Expected: FAIL

**Step 3: Implement pre-filter in enrich_vagas**

In `src/vagas/enrich.py`, modify `enrich_vagas`:

```python
from vagas.filters import is_medical_title

def enrich_vagas(
    vagas: list[Vaga],
    api_key: str | None = None,
    model: str = MODEL,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    if not vagas:
        return 0, 0

    # Layer 1: deterministic pre-filter
    doctor_vagas = []
    non_doctor_count = 0
    for v in vagas:
        if is_medical_title(v.title):
            doctor_vagas.append(v)
        else:
            non_doctor_count += 1
            log.debug("Pre-filtered non-doctor: %s", v.title)

    if not doctor_vagas:
        return 0, non_doctor_count

    key = api_key or _load_api_key()
    client = genai.Client(api_key=key)
    enriched_count = 0

    for start in range(0, len(doctor_vagas), batch_size):
        batch = doctor_vagas[start : start + batch_size]
        log.info("Enriching batch %d-%d of %d", start, start + len(batch), len(doctor_vagas))

        results = None
        for attempt in range(3):
            try:
                results = enrich_batch(client, batch, model=model)
                break
            except genai_errors.ClientError as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = 7 * (attempt + 1)
                    m = re.search(r"retry in (\d+)", err_str)
                    if m:
                        wait = int(m.group(1)) + 2
                    log.info("Rate limited, waiting %ds (attempt %d/3)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    log.warning("Gemini API error on batch %d: %s", start, e)
                    break
            except genai_errors.APIError as e:
                log.warning("Gemini API error on batch %d: %s", start, e)
                break
            except (json.JSONDecodeError, KeyError) as e:
                log.warning("Failed to parse AI response for batch %d: %s", start, e)
                break

        if results is None:
            continue

        for item in results:
            idx = item["index"]
            vaga = batch[idx]

            if not item.get("is_doctor", True):
                non_doctor_count += 1
                log.debug("Non-doctor flagged by AI: %s", vaga.title)
                continue

            specialty = item.get("specialty")
            if specialty and not vaga.specialty:
                vaga.specialty = specialty
                enriched_count += 1
                log.debug("Enriched: %s -> %s", vaga.title, specialty)

        if start + batch_size < len(doctor_vagas):
            time.sleep(2)

    return enriched_count, non_doctor_count
```

**Step 4: Run all enrich tests**

Run: `pytest tests/test_enrich.py -v`
Expected: ALL PASS

**Step 5: Commit**

```
feat: wire deterministic pre-filter into enrichment pipeline
```

---

### Task 4: Delete non-doctor vagas from DB in enrich_only

When enrichment identifies non-doctors (either by pre-filter or AI), delete them from the database instead of leaving them with `specialty=null`.

**Files:**
- Modify: `src/vagas/storage.py` (add `delete_vagas` function)
- Modify: `src/vagas/cli.py:93-120` (enrich_only function)
- Modify: `tests/test_storage.py` (add test for delete)
- Modify: `tests/test_enrich.py` (update enrich_vagas to track non-doctor indices)

**Step 1: Write failing test for delete_vagas**

Add to `tests/test_storage.py`:

```python
def test_delete_vagas(tmp_conn):
    # Insert a vaga, then delete it
    vaga = Vaga(title="Enfermeiro", location="SP", source="test", url="http://x", external_id="del-1")
    upsert_vagas(tmp_conn, [vaga], "test:v1")
    deleted = delete_vagas(tmp_conn, "test", ["del-1"])
    assert deleted == 1
```

Note: adapt to whatever test fixture pattern `test_storage.py` already uses.

**Step 2: Implement delete_vagas in storage.py**

Add to `src/vagas/storage.py`:

```python
def delete_vagas(
    conn: psycopg.Connection,
    source: str,
    external_ids: list[str],
) -> int:
    """Delete vagas by source and external_id. Returns count deleted."""
    if not external_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM vagas WHERE source = %(src)s AND external_id = ANY(%(ids)s)",
            {"src": source, "ids": external_ids},
        )
        return cur.rowcount
```

**Step 3: Make enrich_vagas return non-doctor identifiers**

Change `enrich_vagas` return type from `tuple[int, int]` to `tuple[int, int, list[Vaga]]`:

```python
def enrich_vagas(...) -> tuple[int, int, list[Vaga]]:
    """Returns (enriched_count, non_doctor_count, non_doctor_vagas)."""
    ...
    non_doctor_vagas = []
    ...
    # In pre-filter:
    non_doctor_vagas.append(v)
    ...
    # In AI results:
    non_doctor_vagas.append(vaga)
    ...
    return enriched_count, non_doctor_count, non_doctor_vagas
```

**Step 4: Update enrich_only in cli.py to delete non-doctors**

```python
def enrich_only(source: str | None = None):
    from vagas.enrich import enrich_vagas
    from vagas.storage import delete_vagas

    conn = get_connection()
    ensure_table(conn)

    vagas = load_vagas(conn, source=source, missing_specialty=True)
    log.info("Loaded %d vagas without specialty%s",
             len(vagas), f" (source={source})" if source else "")

    if not vagas:
        log.info("Nothing to enrich")
        conn.close()
        return

    enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas)
    log.info("AI enrichment: %d specialties, %d non-doctor flagged", enriched, non_doc)

    # Write back specialties
    updated = 0
    for v in vagas:
        if v.specialty:
            update_specialty(conn, v.source, v.external_id, v.specialty)
            updated += 1

    # Delete non-doctor vagas
    deleted = 0
    by_source: dict[str, list[str]] = {}
    for v in non_doctor_vagas:
        by_source.setdefault(v.source, []).append(v.external_id)
    for src, ids in by_source.items():
        deleted += delete_vagas(conn, src, ids)

    conn.commit()
    log.info("Updated %d, deleted %d non-doctor vagas", updated, deleted)
    conn.close()
```

**Step 5: Update the crawl `run()` function similarly**

In `cli.py`, update the `run()` function's enrich block to also filter non-doctors from the `vagas` list before upserting:

```python
if enrich:
    from vagas.enrich import enrich_vagas
    enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas)
    total_enriched += enriched
    total_non_doctor += non_doc
    # Remove non-doctors before upsert
    non_doctor_set = {id(v) for v in non_doctor_vagas}
    vagas = [v for v in vagas if id(v) not in non_doctor_set]
```

**Step 6: Fix all callers**

Update all existing tests that call `enrich_vagas` to unpack 3 values instead of 2.

**Step 7: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 8: Commit**

```
feat: delete non-doctor vagas from database during enrichment
```

---

### Task 5: Improve AI prompt — more hints, longer descriptions

Improve the Gemini prompt with synonym hints and increase description truncation.

**Files:**
- Modify: `src/vagas/enrich.py:54-85` (system prompt), `src/vagas/enrich.py:114` (truncation)

**Step 1: Update the system prompt**

Add synonym hints to `_SYSTEM_PROMPT` in `src/vagas/enrich.py`:

```python
# Add after the existing rules (line 71):
- "Médico Ocupacional", "ASO", "PCMSO", "NR-7", "exames ocupacionais" → "Medicina do Trabalho"
- "Ultrassonografista" → "Radiologista"
- "Anestesista" ou "Anestesiologista" → "Anestesiologista"
- "Angiologista" → "Cirurgião Vascular"
- "Emergencista", "Urgentista" → "Clínico Geral"
- Se a vaga lista MÚLTIPLAS especialidades, retorne a PRIMEIRA mencionada
- Priorize descrição sobre título se divergirem
```

**Step 2: Increase description truncation**

Change line 114:

```python
desc = vaga.description[:1000]  # was 500
```

**Step 3: Run integration tests**

Run: `pytest tests/test_enrich.py -m integration -v`
Expected: PASS

**Step 4: Commit**

```
feat: improve AI prompt with synonym hints and increase description window
```

---

### Task 6: Run enrich_only and verify results

End-to-end verification against the real database.

**Step 1: Run enrich_only**

```bash
vagas --enrich-only 2>&1
```

Verify output shows:
- Non-doctor vagas deleted
- Specialties enriched
- No rate limit errors

**Step 2: Check database quality**

```bash
PGPASSWORD='MilhoNaPraia1955*' psql -h db.xbpiwfyctoslazrnzxsd.supabase.co -p 5432 -U postgres -d postgres
```

```sql
-- Should have fewer vagas (non-doctors deleted)
SELECT count(*) FROM vagas;

-- Remaining nulls should be genuinely unclear
SELECT title, company, left(description, 100)
FROM vagas WHERE specialty IS NULL
ORDER BY random() LIMIT 10;

-- No obvious non-doctor titles should remain
SELECT title FROM vagas
WHERE lower(title) LIKE '%enfermeiro%'
   OR lower(title) LIKE '%veterinari%'
   OR lower(title) LIKE '%farmaceutic%'
   OR lower(title) LIKE '%tecnico%';
```

**Step 3: Commit**

```
chore: verify enrichment quality after improvements
```
