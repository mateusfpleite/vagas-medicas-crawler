"""Normalização determinística de campos de vagas médicas."""

import re

from vagas.utils import strip_accents

# Strip "(a)", "(A)", "(o)" at start or end
_PAREN_GENDER_RE = re.compile(r"\(a\)|\(o\)", re.IGNORECASE)

# Suffixes that describe context, not specialty (stripped before mapping)
_CONTEXT_SUFFIXES_RE = re.compile(
    r"\s+(?:Presencial|Telemedicina|Ambulatorial|Diarista|UAPS|PNAR"
    r"|Ecocardiografista|Plantão Médico|\(RETAGUARDA\)|GERAL"
    r"|Horizontal|Pedi[áa]tric[oa]?|Infantil|com\s+.+)$",
    re.IGNORECASE,
)


def _clean(raw: str) -> str:
    """Lowercase, strip accents, remove gender markers and context suffixes."""
    s = _PAREN_GENDER_RE.sub("", raw.strip())
    s = _CONTEXT_SUFFIXES_RE.sub("", s)
    # Strip wrapping parens: "(Clínico)" -> "Clínico"
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    s = strip_accents(s.strip().lower())
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)
    return s


# Mapping: cleaned key -> canonical specialty
# Keys are lowercase, accent-stripped
_SPECIALTY_MAP: dict[str, str] = {
    # Cardiologista
    "cardiologista": "Cardiologista",
    "cardilogista": "Cardiologista",  # typo
    "ecocardiografista": "Cardiologista",
    # Cirurgião
    "cirurgiao": "Cirurgião Geral",
    "cirurgiao geral": "Cirurgião Geral",
    "cirurgiao vascular": "Cirurgião Vascular",
    "cirurgiao cabeca pescoco": "Cirurgião Geral",
    "cirurgiao cabeca e pescoco": "Cirurgião Geral",
    # Clínico Geral
    "clinico": "Clínico Geral",
    "clinico geral": "Clínico Geral",
    "clinica medica": "Clínico Geral",
    "generalista": "Clínico Geral",
    # Dermatologista
    "dermatologista": "Dermatologista",
    "dermatologista pediatra": "Dermatologista",
    # Endocrinologista
    "endocrinologista": "Endocrinologista",
    # Geriatra
    "geriatra": "Geriatra",
    # Ginecologista
    "ginecologista": "Ginecologista",
    "ginecologista e obstetra": "Ginecologista",
    "tocoginecologista": "Ginecologista",
    # Infectologista
    "infectologista": "Infectologista",
    # Intensivista
    "intensivista": "Intensivista",
    "intensivista pediatrico": "Intensivista",
    # Medicina do Trabalho
    "medicina do trabalho": "Medicina do Trabalho",
    "do trabalho": "Medicina do Trabalho",
    "do trabalho/ medico de familia": "Medicina do Trabalho",
    # Medicina de Família
    "medicina de familia": "Medicina de Família",
    "de saude da familia": "Medicina de Família",
    "esf": "Medicina de Família",
    # Neurologista
    "neurologista": "Neurologista",
    "neurologista infantil": "Neurologista",
    # Oftalmologista
    "oftalmologista": "Oftalmologista",
    # Ortopedista
    "ortopedista": "Ortopedista",
    # Pediatra
    "pediatra": "Pediatra",
    # Plantonista
    "plantonista": "Plantonista",
    # Pneumologista
    "pneumologista": "Pneumologista",
    # Psiquiatra
    "psiquiatra": "Psiquiatra",
    # Medicina do Trabalho (synonyms)
    "medicina ocupacional": "Medicina do Trabalho",
    "medico examinador ocupacional": "Medicina do Trabalho",
    # Radiologista (synonyms)
    "radiologista": "Radiologista",
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
    "oncologista": "Oncologista",
    # Ginecologista (standalone obstetra)
    "obstetra": "Ginecologista",
    # Other missing identities
    "nefrologista": "Nefrologista",
    "neonatologista": "Neonatologista",
    "gastroenterologista": "Gastroenterologista",
    "fisiatra": "Fisiatra",
    "proctologista": "Proctologista",
    "reumatologista": "Reumatologista",
    "urologista": "Urologista",
}

# Values that should become None (not real specialties)
_NULLIFY = {
    "em goiania",
    "examinador",
    "saude",
}


def normalize_specialty(raw: str | None) -> str | None:
    """Normalize a raw specialty string to a canonical form.

    Returns None if the value is not a recognized medical specialty.
    """
    if not raw:
        return None

    cleaned = _clean(raw)
    if not cleaned:
        return None

    if cleaned in _NULLIFY:
        return None

    return _SPECIALTY_MAP.get(cleaned)
