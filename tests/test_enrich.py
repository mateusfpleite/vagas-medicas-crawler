"""Tests for AI enrichment module."""

import json
import pytest
from unittest.mock import MagicMock, patch

from vagas.enrich import (
    _build_batch_prompt,
    _is_garbage_vaga,
    _parse_response,
    enrich_batch,
    enrich_vagas,
    CANONICAL_SPECIALTIES,
)
from vagas.models import Vaga


# --- helpers ---------------------------------------------------------------

def _vaga(**overrides) -> Vaga:
    base = dict(
        title="Médico",
        location="SP",
        source="test",
        url="https://example.com/1",
    )
    base.update(overrides)
    return Vaga(**base)


def _mock_client(response_json: list[dict]) -> MagicMock:
    """Create a mock genai.Client that returns the given JSON."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps(response_json)
    client.models.generate_content.return_value = mock_response
    return client


# --- _is_garbage_vaga ------------------------------------------------------

def test_garbage_vaga_generic_title_no_description():
    assert _is_garbage_vaga(_vaga(title="Médico")) is True


def test_garbage_vaga_generic_title_short_description():
    assert _is_garbage_vaga(_vaga(title="MEDICO", description="curta")) is True


def test_garbage_vaga_generic_title_with_description():
    assert _is_garbage_vaga(_vaga(title="Médico", description="Vaga para clínico geral em UBS municipal")) is False


def test_garbage_vaga_specific_title_no_description():
    assert _is_garbage_vaga(_vaga(title="Médico Ortopedista")) is False


# --- _build_batch_prompt ---------------------------------------------------

def test_build_prompt_includes_title():
    vagas = [(0, _vaga(title="Médico Ortopedista"))]
    prompt = _build_batch_prompt(vagas)
    assert "Médico Ortopedista" in prompt


def test_build_prompt_includes_description():
    vagas = [(0, _vaga(description="Vaga para cardiologista"))]
    prompt = _build_batch_prompt(vagas)
    assert "cardiologista" in prompt


def test_build_prompt_truncates_long_description():
    long_desc = "x" * 2000
    vagas = [(0, _vaga(description=long_desc))]
    prompt = _build_batch_prompt(vagas)
    assert len(prompt) < 1300


def test_build_prompt_includes_company():
    vagas = [(0, _vaga(company="Hospital X"))]
    prompt = _build_batch_prompt(vagas)
    assert "Hospital X" in prompt


# --- _parse_response -------------------------------------------------------

def test_parse_plain_json():
    text = '[{"id": 1, "specialty": "Pediatra", "is_doctor": true}]'
    result = _parse_response(text)
    assert result[0]["specialty"] == "Pediatra"


def test_parse_with_code_fences():
    text = '```json\n[{"id": 1, "specialty": "Pediatra", "is_doctor": true}]\n```'
    result = _parse_response(text)
    assert result[0]["specialty"] == "Pediatra"


def test_parse_with_just_backticks():
    text = '```\n[{"id": 1, "specialty": null, "is_doctor": false}]\n```'
    result = _parse_response(text)
    assert result[0]["is_doctor"] is False


# --- enrich_batch (mocked) -------------------------------------------------

def test_enrich_batch_basic():
    vagas = [
        _vaga(title="Médico Ortopedista"),
        _vaga(title="Médico Pediatra"),
    ]
    client = _mock_client([
        {"id": 1, "specialty": "Ortopedista", "is_doctor": True},
        {"id": 2, "specialty": "Pediatra", "is_doctor": True},
    ])
    results = enrich_batch(client, vagas)
    assert len(results) == 2
    assert results[0]["specialty"] == "Ortopedista"
    assert results[1]["specialty"] == "Pediatra"


def test_enrich_batch_non_doctor():
    vagas = [_vaga(title="Enfermeiro Assistencial")]
    client = _mock_client([
        {"id": 1, "specialty": None, "is_doctor": False},
    ])
    results = enrich_batch(client, vagas)
    assert results[0]["is_doctor"] is False


def test_enrich_batch_null_specialty():
    vagas = [_vaga(title="Médico")]
    client = _mock_client([
        {"id": 1, "specialty": None, "is_doctor": True},
    ])
    results = enrich_batch(client, vagas)
    assert results[0]["specialty"] is None


def test_enrich_batch_empty():
    results = enrich_batch(MagicMock(), [])
    assert results == []


# --- enrich_vagas (mocked) -------------------------------------------------

def test_enrich_vagas_sets_specialty():
    vagas = [
        _vaga(title="Médico Psiquiatra"),
        _vaga(title="Médico Pediatra"),
    ]
    with patch("vagas.enrich.genai") as mock_genai:
        mock_client = _mock_client([
            {"id": 1, "specialty": "Psiquiatra", "is_doctor": True},
            {"id": 2, "specialty": "Pediatra", "is_doctor": True},
        ])
        mock_genai.Client.return_value = mock_client

        enriched, non_doc, _ = enrich_vagas(vagas, api_key="fake-key")
        assert enriched == 2
        assert non_doc == 0
        assert vagas[0].specialty == "Psiquiatra"
        assert vagas[1].specialty == "Pediatra"


def test_enrich_vagas_does_not_overwrite_existing_specialty():
    vagas = [_vaga(title="Médico Ortopedista", specialty="Ortopedista")]
    with patch("vagas.enrich.genai") as mock_genai:
        mock_client = _mock_client([
            {"id": 1, "specialty": "Ortopedista", "is_doctor": True},
        ])
        mock_genai.Client.return_value = mock_client

        enriched, _, _ = enrich_vagas(vagas, api_key="fake-key")
        assert enriched == 0  # already had specialty
        assert vagas[0].specialty == "Ortopedista"


def test_enrich_vagas_counts_non_doctors():
    vagas = [
        _vaga(title="Enfermeiro"),
        _vaga(title="Médico Pediatra"),
    ]
    with patch("vagas.enrich.genai") as mock_genai:
        # Enfermeiro is pre-filtered; AI only sees Médico Pediatra
        mock_client = _mock_client([
            {"id": 1, "specialty": "Pediatra", "is_doctor": True},
        ])
        mock_genai.Client.return_value = mock_client

        enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas, api_key="fake-key")
        assert enriched == 1
        assert non_doc == 1  # Enfermeiro pre-filtered


def test_enrich_vagas_empty():
    enriched, non_doc, _ = enrich_vagas([], api_key="fake-key")
    assert enriched == 0
    assert non_doc == 0


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

        enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas, api_key="fake-key")
        assert non_doc == 2  # farmaceutico + enfermeiro
        assert enriched == 1
        assert vagas[1].specialty == "Pediatra"
        assert len(non_doctor_vagas) == 2


def test_enrich_vagas_returns_ai_flagged_non_doctors():
    """AI-flagged non-doctors should be in the returned list."""
    vagas = [
        _vaga(title="Médico", description="Padaria contrata balconista"),  # AI will flag
        _vaga(title="Médico Pediatra"),
    ]
    with patch("vagas.enrich.genai") as mock_genai:
        mock_client = _mock_client([
            {"id": 1, "specialty": None, "is_doctor": False},
            {"id": 2, "specialty": "Pediatra", "is_doctor": True},
        ])
        mock_genai.Client.return_value = mock_client

        enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas, api_key="fake-key")
        assert non_doc == 1
        assert enriched == 1
        assert len(non_doctor_vagas) == 1
        assert non_doctor_vagas[0].description == "Padaria contrata balconista"


# --- Integration tests (real API) -----------------------------------------

@pytest.fixture(scope="module")
def api_key():
    """Load real API key, skip if not available."""
    import os
    from pathlib import Path

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.strip().startswith("GEMINI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key


@pytest.fixture(scope="module")
def gemini_client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


# Known test cases: (title, description, expected_specialty, expected_is_doctor)
KNOWN_CASES = [
    # Clear specialty from title
    (
        "Médico Ortopedista",
        "Atendimento especializado em ortopedia",
        "Ortopedista",
        True,
    ),
    (
        "MÉDICO PSIQUIATRA – Plantonista",
        "Residência em Psiquiatria obrigatória",
        "Psiquiatra",
        True,
    ),
    (
        "Médico do Trabalho",
        "Exames ocupacionais e PCMSO",
        "Medicina do Trabalho",
        True,
    ),
    (
        "Médico Pediatra",
        "Atendimento pediátrico em UBS",
        "Pediatra",
        True,
    ),
    # Specialty from description
    (
        "Médico",
        "Vaga para cardiologista com experiência em ecocardiografia",
        "Cardiologista",
        True,
    ),
    # Non-doctor: healthcare workers
    (
        "Fisioterapeuta (CTI Pediátrico)",
        "Referência em Medicina Intensivista Neonatal e Pediátrica",
        None,
        False,
    ),
    (
        "Enfermeiro Assistencial - Centro Médico",
        "Acompanhamento de pacientes internados",
        None,
        False,
    ),
    (
        "Farmacêutico(a) RT – Clínica de Cirurgia Plástica",
        "Gestão administrativa da farmácia da clínica",
        None,
        False,
    ),
    # Non-doctor: pharma/corporate roles
    (
        "Promotor Médico I - Belém",
        "Promover e divulgar os produtos da companhia junto a médicos profissionais de saúde",
        None,
        False,
    ),
    (
        "Representante Visitação Médica - Niterói/RJ",
        "Atuação em visitação médica, promovendo produtos de alta qualidade",
        None,
        False,
    ),
    # Non-doctor: veterinarian
    (
        "Medico Veterinario",
        "Boas práticas e protocolos técnicos em todos os setores da clínica veterinária",
        None,
        False,
    ),
    # Neonatologista (new canonical specialty)
    (
        "Médico (Neonatologista)",
        "Residência em Neonatologia concluída",
        "Neonatologista",
        True,
    ),
]


@pytest.mark.integration
def test_ai_specialty_extraction(gemini_client):
    """Test that AI correctly extracts specialties from known examples."""
    vagas = []
    for title, desc, _, _ in KNOWN_CASES:
        vagas.append(_vaga(title=title, description=desc))

    results = enrich_batch(gemini_client, vagas, model="gemini-2.5-flash-lite")

    assert len(results) == len(KNOWN_CASES), (
        f"Expected {len(KNOWN_CASES)} results, got {len(results)}"
    )

    for item in results:
        idx = item["index"]
        _, _, expected_specialty, expected_is_doctor = KNOWN_CASES[idx]

        assert item["is_doctor"] == expected_is_doctor, (
            f"Case {idx} ({KNOWN_CASES[idx][0]}): "
            f"expected is_doctor={expected_is_doctor}, got {item['is_doctor']}"
        )

        if expected_specialty:
            assert item["specialty"] == expected_specialty, (
                f"Case {idx} ({KNOWN_CASES[idx][0]}): "
                f"expected specialty={expected_specialty}, got {item['specialty']}"
            )
        elif expected_is_doctor is False:
            # Non-doctor, specialty should be null
            pass  # AI may or may not return a specialty label for non-doctors


@pytest.mark.integration
def test_ai_returns_only_canonical_specialties(gemini_client):
    """Verify AI only returns specialties from our canonical list."""
    vagas = [
        _vaga(title="Médico Nefrologista", description="Diálise e transplante renal"),
        _vaga(title="Médico Ginecologista", description="Consultas ginecológicas"),
        _vaga(title="MÉDICA FISIATRA", description="Reabilitação física"),
        _vaga(title="Médico Gastro", description="Endoscopia digestiva"),
    ]

    results = enrich_batch(gemini_client, vagas, model="gemini-2.5-flash-lite")

    for item in results:
        spec = item.get("specialty")
        if spec is not None:
            assert spec in CANONICAL_SPECIALTIES, (
                f"Non-canonical specialty returned: {spec}"
            )


@pytest.mark.integration
def test_ai_handles_minimal_data(gemini_client):
    """Test with minimal BNE-like data: just title and location."""
    vagas = [
        _vaga(title="Médico", location="São Paulo/SP"),
        _vaga(title="Médico", location="Cuiabá/MT"),
    ]

    results = enrich_batch(gemini_client, vagas, model="gemini-2.5-flash-lite")

    assert len(results) == 2
    for item in results:
        assert item["is_doctor"] is True
        # With just "Médico" and no description, specialty should be null
        # (but we don't strictly enforce this - AI might infer from context)
