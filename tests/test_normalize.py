import pytest

from vagas.normalize import normalize_specialty


@pytest.mark.parametrize("raw,expected", [
    # Casing normalization
    ("Ginecologista", "Ginecologista"),
    ("GINECOLOGISTA", "Ginecologista"),
    ("ginecologista", "Ginecologista"),
    ("CARDIOLOGISTA", "Cardiologista"),
    ("Cardiologista", "Cardiologista"),
    # Typos
    ("Cardilogista", "Cardiologista"),
    # Parenthetical prefix
    ("(a) ginecologista", "Ginecologista"),
    ("(A) DO TRABALHO", "Medicina do Trabalho"),
    ("(a) Dermatologista Pediatra", "Dermatologista"),
    ("(Clínico)", "Clínico Geral"),  # wrapping parens stripped -> "Clínico" -> Clínico Geral
    # Context suffixes stripped
    ("Neurologista Presencial", "Neurologista"),
    ("Neurologista Telemedicina", "Neurologista"),
    ("Endocrinologista Telemedicina", "Endocrinologista"),
    ("Geriatra Presencial", "Geriatra"),
    ("Dermatologista Presencial", "Dermatologista"),
    ("Infectologista Telemedicina", "Infectologista"),
    ("Pneumologista Telemedicina", "Pneumologista"),
    ("Psiquiatra Ambulatorial", "Psiquiatra"),
    ("INTENSIVISTA DIARISTA", "Intensivista"),
    ("Pediatra UAPS", "Pediatra"),
    ("Ginecologista PNAR", "Ginecologista"),
    ("OFTALMOLOGISTA (RETAGUARDA)", "Oftalmologista"),
    ("OFTALMOLOGISTA GERAL", "Oftalmologista"),
    ("Cardiologista Ecocardiografista", "Cardiologista"),
    ("Neurologista com especialização em neurofisiologia", "Neurologista"),
    ("Clínica Médica Horizontal", "Clínico Geral"),
    # Subespecialidades -> pai
    ("NEUROLOGISTA INFANTIL", "Neurologista"),
    ("Intensivista Pediátrico(a)", "Intensivista"),
    ("Cirurgião Cabeça Pescoço", "Cirurgião Geral"),
    # Direct mappings
    ("DO TRABALHO", "Medicina do Trabalho"),
    ("do Trabalho", "Medicina do Trabalho"),
    ("Generalista", "Clínico Geral"),
    ("GENERALISTA", "Clínico Geral"),
    ("TOCOGINECOLOGISTA", "Ginecologista"),
    ("Ginecologista e Obstetra", "Ginecologista"),
    ("ESF", "Medicina de Família"),
    ("de Saúde da Família", "Medicina de Família"),
    ("do Trabalho/ Médico de Família", "Medicina do Trabalho"),
    ("Medicina do Trabalho", "Medicina do Trabalho"),
    ("Medicina de Família", "Medicina de Família"),
    ("CIRURGIAO GERAL", "Cirurgião Geral"),
    ("Plantonista Plantão Médico", "Plantonista"),
    # Occupational medicine synonyms
    ("Medicina Ocupacional", "Medicina do Trabalho"),
    ("Médico Examinador Ocupacional", "Medicina do Trabalho"),
    # Radiology / imaging
    ("Ultrassonografista", "Radiologista"),
    ("Radiologista", "Radiologista"),
    # Angiologista -> Cirurgião Vascular
    ("Angiologista", "Cirurgião Vascular"),
    # Anestesiologista
    ("Anestesista", "Anestesiologista"),
    ("Anestesiologista", "Anestesiologista"),
    # Emergency -> Clínico Geral
    ("Emergencista", "Clínico Geral"),
    ("Urgentista", "Clínico Geral"),
    # Hematologista -> Oncologista
    ("Hematologista", "Oncologista"),
    # Obstetra standalone
    ("Obstetra", "Ginecologista"),
    # Previously missing identity mappings
    ("Nefrologista", "Nefrologista"),
    ("Neonatologista", "Neonatologista"),
    ("Gastroenterologista", "Gastroenterologista"),
    ("Fisiatra", "Fisiatra"),
    ("Proctologista", "Proctologista"),
    ("Reumatologista", "Reumatologista"),
    ("Urologista", "Urologista"),
    ("Oncologista", "Oncologista"),
    # Nullify (not real specialties)
    ("em Goiânia", None),
    ("Examinador", None),
    ("Saúde", None),
    ("(a)", None),
    # Ecocardiografista -> Cardiologista
    ("Ecocardiografista", "Cardiologista"),
    ("ecocardiografista", "Cardiologista"),
    # None/empty input
    (None, None),
    ("", None),
    ("  ", None),
])
def test_normalize_specialty(raw, expected):
    assert normalize_specialty(raw) == expected, f"normalize_specialty({raw!r}) should be {expected!r}"
