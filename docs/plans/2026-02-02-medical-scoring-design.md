# Medical Scoring Module — Design

## Problem

Current filters (regex allowlist + blocklist) cannot distinguish "Médico Cardiologista" (profession) from "Secretária Clínica Médica" (adjective). In the InfoJobs dry-run, 10 of 27 unique titles (~37%) were false positives — non-doctor jobs that contain "médic" in the title.

## Solution

A scoring module (`src/vagas/scoring.py`) that assigns a numeric score (0.0–1.0) to each vaga indicating probability of being a doctor position. Pure function, no I/O, no dependencies beyond stdlib + re.

```python
def medical_score(title: str, description: str | None = None) -> float
```

## Scoring Rules

### Title signals

| Signal | Weight | Example |
|--------|--------|---------|
| "Médico/a" as first word | +0.4 | "Médico Cardiologista" |
| "Médico/a" after hyphen | +0.3 | "Vaga - Médico do Trabalho" |
| "Médico(a)" with gender flex | +0.2 | "Médico(a) Plantonista" |
| Known specialty in title | +0.2 | "... Pediatra", "... Psiquiatra" |
| Non-doctor job as first word | -0.4 | "Secretária", "Closer", "Consultor" |
| "Clínica/Área/Equipe Médica" | -0.3 | adjective of workplace |
| "Propagandista Médico" | -0.3 | pharma rep |
| "Médico" not first word, not after hyphen | -0.2 | ambiguous position |

### Description signals (post-detail only)

| Signal | Weight | Example |
|--------|--------|---------|
| CRM required | +0.3 | "necessário CRM ativo" |
| RQE mentioned | +0.3 | "RQE em cardiologia" |
| Known specialty | +0.2 | "cardiologista" in description |
| Clinical procedures | +0.15 | "prescrição", "diagnóstico", "laudo", "cirurgia" |
| Healthcare facility | +0.1 | "hospital", "UBS", "UPA", "pronto-socorro" |
| "Plantão" with hours | +0.1 | "plantão 12h", "plantão 24h" |
| "Vendas"/"comercial"/"metas" | -0.3 | sales role |
| "Indústria farmacêutica" | -0.3 | pharma rep |
| "Visitação/visita médica" | -0.2 | commercial rep |
| "Atendimento ao cliente" | -0.2 | customer service |
| Low education required | -0.2 | "ensino médio", "técnico em" |
| "Experiência em vendas/negociação" | -0.2 | sales signal |

## Thresholds

- `TITLE_THRESHOLD = 0.4` — pre-detail filter (permissive)
- `FULL_THRESHOLD = 0.5` — post-detail filter (stricter)

## Pipeline Integration

### Pre-detail (inside each spider's parse_listing)

After existing regex + blocklist filters, apply `medical_score(title) >= TITLE_THRESHOLD`. Saves HTTP requests by discarding obvious non-doctors before detail fetch.

### Post-detail (centralized in cli.py)

After `crawl()` returns, apply `medical_score(title, description) >= FULL_THRESHOLD`. Discards remaining false positives before enrich/upsert. Runs in `cli.py` alongside normalize_specialty and normalize_location — DRY across all spiders.

### Relationship with existing filters

- `filters.py` blocklist stays as fast first-pass filter
- `scoring.py` is an additional layer that catches ambiguous cases the blocklist misses
- AI enrichment (Gemini) remains as final arbiter for edge cases

## Testing

- Pure function tests: known-doctor titles score >= 0.8, known-non-doctor < 0.4
- Title + description combination tests
- Regression tests with all 10 real false positives from InfoJobs dry-run
- Integration tests verifying spiders discard low-score vagas
