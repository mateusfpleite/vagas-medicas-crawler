"""AI-powered enrichment of medical job listings using Gemini."""

import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors

from vagas.filters import is_medical_title
from vagas.models import Vaga

log = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

# Canonical specialties — AI must pick from this list or return null
CANONICAL_SPECIALTIES = [
    "Anestesiologista",
    "Cardiologista",
    "Cirurgião Geral",
    "Cirurgião Vascular",
    "Clínico Geral",
    "Dermatologista",
    "Endocrinologista",
    "Fisiatra",
    "Gastroenterologista",
    "Geriatra",
    "Ginecologista",
    "Infectologista",
    "Intensivista",
    "Medicina de Família",
    "Medicina do Esporte",
    "Medicina do Trabalho",
    "Nefrologista",
    "Neonatologista",
    "Neurologista",
    "Oftalmologista",
    "Oncologista",
    "Ortopedista",
    "Otorrinolaringologista",
    "Pediatra",
    "Plantonista",
    "Pneumologista",
    "Proctologista",
    "Psiquiatra",
    "Radiologista",
    "Reumatologista",
    "Urologista",
]

MODEL = "gemini-2.5-flash-lite"
BATCH_SIZE = 50  # vagas per API call (~300 tokens/vaga with 1000-char descriptions)

_SYSTEM_PROMPT = f"""Você é um classificador de vagas médicas brasileiras.

Para cada vaga, determine:
1. Se a vaga é para MÉDICO (não enfermeiro, fisioterapeuta, farmacêutico, técnico, etc.)
2. A especialidade médica, escolhendo APENAS da lista abaixo:

{chr(10).join(f'- {s}' for s in CANONICAL_SPECIALTIES)}

Regras:
- Se a vaga NÃO é para médico, retorne is_doctor=false e specialty=null
- Se é para médico mas a especialidade não está clara, retorne specialty=null
- "Médico Plantonista" sem contexto → specialty=null (pode ser qualquer especialidade)
- "Médico PSF" ou "Saúde da Família" → "Medicina de Família"
- "Médico Auditor", "Médico Ocupacional", "ASO", "PCMSO", "NR-7", "exames ocupacionais" → "Medicina do Trabalho"
- "Ultrassonografista" → "Radiologista"
- "Anestesista" ou "Anestesiologista" → "Anestesiologista"
- "Angiologista" → "Cirurgião Vascular"
- "Emergencista", "Urgentista" → "Clínico Geral"
- "Clínica Médica" → "Clínico Geral"
- "Ecocardiografista" → "Cardiologista"
- "Médico Offshore" ou trabalho embarcado → "Medicina do Trabalho"
- Se a vaga lista MÚLTIPLAS especialidades, retorne a PRIMEIRA mencionada
- Use o título E a descrição para inferir a especialidade
- Quando título e descrição divergem, priorize a descrição

NÃO são vagas de médico (is_doctor=false):
- Enfermeiro, Fisioterapeuta, Farmacêutico, Técnico de enfermagem
- Médico Veterinário (veterinário NÃO é médico humano)
- "Promotor Médico" (representante comercial farmacêutico)
- "Representante Visitação Médica" (vendedor de indústria farmacêutica)
- "Analista Médico Científico" (cargo corporativo, não clínico)
- "Analista de Relacionamento Médico" (cargo corporativo)
- "Executivo de Relacionamento Médico" (cargo corporativo)
- "Docente Médico" sem prática clínica (cargo acadêmico)
- Qualquer cargo que não envolva atendimento clínico/cirúrgico a pacientes

Responda APENAS com um JSON array (sem markdown, sem code fences). Cada elemento:
{{"id": <número>, "specialty": "<especialidade ou null>", "is_doctor": true/false}}"""


_GENERIC_TITLE_RE = re.compile(r"^m[ée]dic[oa]$", re.IGNORECASE)


def _is_garbage_vaga(vaga: Vaga) -> bool:
    """Detect vagas with generic title and no useful description (e.g. failed BNE fetches)."""
    if not _GENERIC_TITLE_RE.match(vaga.title.strip()):
        return False
    desc = (vaga.description or "").strip()
    return len(desc) < 20


def _load_api_key() -> str:
    """Load GEMINI_API_KEY from environment or .env file."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == "GEMINI_API_KEY":
                    return v.strip()
    raise RuntimeError("GEMINI_API_KEY not set")


def _build_batch_prompt(vagas: list[tuple[int, Vaga]]) -> str:
    """Build the user prompt for a batch of vagas."""
    lines = []
    for idx, (num, vaga) in enumerate(vagas, 1):
        parts = [f"{idx}. TÍTULO: {vaga.title}"]
        if vaga.company:
            parts.append(f"   EMPRESA: {vaga.company}")
        if vaga.location:
            parts.append(f"   LOCAL: {vaga.location}")
        if vaga.description:
            # Truncate long descriptions
            desc = vaga.description[:1000]
            parts.append(f"   DESCRIÇÃO: {desc}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _parse_response(text: str) -> list[dict]:
    """Parse AI response, handling possible markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        # Remove code fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def enrich_batch(
    client: genai.Client,
    vagas: list[Vaga],
    model: str = MODEL,
) -> list[dict]:
    """Enrich a batch of vagas with AI-extracted specialty.

    Returns list of dicts with keys: index, specialty, is_doctor.
    Index is 0-based position in the input list.
    """
    if not vagas:
        return []

    numbered = list(enumerate(vagas))
    prompt = _build_batch_prompt(numbered)

    response = client.models.generate_content(
        model=model,
        contents=f"{_SYSTEM_PROMPT}\n\nVagas:\n\n{prompt}",
    )

    results = _parse_response(response.text)

    enriched = []
    for item in results:
        ai_idx = item.get("id", 0) - 1  # 1-based to 0-based
        if 0 <= ai_idx < len(vagas):
            enriched.append({
                "index": ai_idx,
                "specialty": item.get("specialty"),
                "is_doctor": item.get("is_doctor", True),
            })
    return enriched


def enrich_vagas(
    vagas: list[Vaga],
    api_key: str | None = None,
    model: str = MODEL,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int, list[Vaga]]:
    """Enrich vagas in-place with AI-extracted fields.

    Returns (enriched_count, non_doctor_count, non_doctor_vagas).
    """
    if not vagas:
        return 0, 0, []

    # Layer 1: deterministic pre-filter
    doctor_vagas = []
    non_doctor_count = 0
    non_doctor_vagas: list[Vaga] = []
    for v in vagas:
        if not is_medical_title(v.title):
            non_doctor_count += 1
            non_doctor_vagas.append(v)
            log.debug("Pre-filtered non-doctor: %s", v.title)
        elif _is_garbage_vaga(v):
            non_doctor_count += 1
            non_doctor_vagas.append(v)
            log.debug("Pre-filtered garbage vaga: %s", v.title)
        else:
            doctor_vagas.append(v)

    if not doctor_vagas:
        return 0, non_doctor_count, non_doctor_vagas

    key = api_key or _load_api_key()
    # Force IPv4 to avoid hanging on broken IPv6 (getaddrinfo returns IPv6 first,
    # each times out ~130s before falling back to IPv4).
    transport = httpx.HTTPTransport(local_address="0.0.0.0")
    http_client = httpx.Client(transport=transport, timeout=httpx.Timeout(60.0, connect=5.0))
    client = genai.Client(
        api_key=key,
        http_options={"httpx_client": http_client},
    )

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
                    # Extract retry delay from error message
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
                non_doctor_vagas.append(vaga)
                log.debug("Non-doctor flagged: %s", vaga.title)
                continue

            from vagas.normalize import normalize_specialty
            raw_spec = item.get("specialty")
            specialty = normalize_specialty(raw_spec) or raw_spec
            if specialty and not vaga.specialty:
                vaga.specialty = specialty
                enriched_count += 1
                log.debug("Enriched: %s -> %s", vaga.title, specialty)

        # Small delay between batches to respect rate limits
        if start + batch_size < len(doctor_vagas):
            time.sleep(2)

    return enriched_count, non_doctor_count, non_doctor_vagas
