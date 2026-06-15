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
    ("MÉDICO OFFSHORE - SÍSMICA", True),
    # Should REJECT (non-doctor healthcare)
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
    # Should REJECT (non-doctor corporate/sales in medical context)
    ("Gestora Comercial (Clínica de Cirurgia Plástica)", False),
    ("ATENDENTE CLINICA CIRURGIA PLASTICA", False),
    ("Representante Visitação Médica", False),
    ("Promotor Médico", False),
    ("Analista Médico Científico", False),
    ("Executivo de Relacionamento Médico", False),
    # Should REJECT (veterinarian)
    ("Medico Veterinario- São Judas", False),
    ("MEDICO VETERINÁRIO", False),
    # Should REJECT (non-medical roles)
    ("Balconista", False),
    ("Vendedor", False),
    ("Auxiliar de médico", False),
    # Edge cases
    ("", False),
    ("   ", False),
])
def test_is_medical_title(title, expected):
    assert is_medical_title(title) == expected, f"is_medical_title({title!r}) should be {expected}"
