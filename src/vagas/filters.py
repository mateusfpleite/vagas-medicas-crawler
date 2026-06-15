"""Deterministic pre-filters for medical job listings."""

import re

from vagas.utils import strip_accents


# Titles that are clearly NOT doctor positions, even if "médico" appears in context
_NON_DOCTOR_RE = re.compile(
    r"\b("
    r"veterinari[oa]"
    r"|enfermeiro|enfermeira"
    r"|farmaceutic[oa]"
    r"|fisioterapeuta"
    r"|nutricionista"
    r"|psicologo[a]?"
    r"|biomedic[oa]"
    r"|fonoaudiolog[oa]"
    r"|tecnic[oa]\b"
    r"|terapeuta\s+ocupacional"
    r"|assistente\s+social"
    r"|atendente"
    r"|balconista"
    r"|vendedor[a]?"
    r"|auxiliar"
    r"|gestor[a]?"
    r"|promotor[a]?\s+medic[oa]"
    r"|representante\s+visitacao"
    r"|analista\s+medic[oa]"
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

    normalized = strip_accents(title)

    if _NON_DOCTOR_RE.search(normalized):
        return False

    return True
