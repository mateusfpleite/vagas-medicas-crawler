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
