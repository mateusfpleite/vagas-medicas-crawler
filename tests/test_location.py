"""Tests for location parsing and normalization."""

from unittest.mock import patch

import pytest

from vagas.location import parse_location, normalize_location, _build_lookup


# --- parse_location tests ---

@pytest.mark.parametrize("raw, expected", [
    # All 4 separator formats
    ("São Paulo, SP", ("São Paulo", "SP")),
    ("São Paulo / SP", ("São Paulo", "SP")),
    ("São Paulo/SP", ("São Paulo", "SP")),
    ("Curitiba - PR", ("Curitiba", "PR")),
    # City-only (Indeed bare cities)
    ("São Paulo", ("São Paulo", None)),
    ("Fortaleza", ("Fortaleza", None)),
    # Special values
    ("Remoto", (None, None)),
    ("remoto", (None, None)),
    ("Brasil", (None, None)),
    ("Home Office", (None, None)),
    (None, (None, None)),
    ("", (None, None)),
    ("   ", (None, None)),
    # Whitespace handling
    ("  São Paulo , SP  ", ("São Paulo", "SP")),
    # Bare UF codes (PCI spider fallback)
    ("MG", (None, "MG")),
    ("SP", (None, "SP")),
    ("rj", (None, "RJ")),
])
def test_parse_location(raw, expected):
    assert parse_location(raw) == expected


# --- normalize_location tests (with mocked IBGE data) ---

_FAKE_IBGE = [
    {
        "nome": "São Paulo",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "SP"}}},
    },
    {
        "nome": "Florianópolis",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "SC"}}},
    },
    {
        "nome": "Curitiba",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "PR"}}},
    },
    {
        "nome": "Fortaleza",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "CE"}}},
    },
    {
        "nome": "Boa Vista",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "RR"}}},
    },
    {
        "nome": "Boa Vista",
        "microrregiao": {"mesorregiao": {"UF": {"sigla": "PB"}}},
    },
]


@pytest.fixture(autouse=True)
def _mock_ibge():
    """Inject fake IBGE data into module-level lookup tables."""
    import vagas.location as loc

    lookup, lookup_by_name = _build_lookup(_FAKE_IBGE)
    old_lookup, old_by_name = loc._LOOKUP, loc._LOOKUP_BY_NAME
    loc._LOOKUP = lookup
    loc._LOOKUP_BY_NAME = lookup_by_name
    yield
    loc._LOOKUP = old_lookup
    loc._LOOKUP_BY_NAME = old_by_name


@pytest.mark.parametrize("raw, expected_city, expected_state", [
    # No accents → finds official name
    ("sao paulo, SP", "São Paulo", "SP"),
    # Uppercase → finds official name
    ("SAO PAULO, SP", "São Paulo", "SP"),
    # BNE format + accent restoration
    ("florianopolis/SC", "Florianópolis", "SC"),
    # City-only → unambiguous IBGE match
    ("São Paulo", "São Paulo", "SP"),
    ("Fortaleza", "Fortaleza", "CE"),
    # Ambiguous city-only → delegate to AI
    ("Boa Vista", None, None),
    # Ambiguous city with state → resolves
    ("Boa Vista, RR", "Boa Vista", "RR"),
    ("Boa Vista - PB", "Boa Vista", "PB"),
    # Special values
    ("Remoto", None, None),
    (None, None, None),
    # Unknown city with state → raw + UF (AI can refine)
    ("Cidade Inventada, MG", "Cidade Inventada", "MG"),
    # Unknown city without state → delegate to AI
    ("Cidade Inventada", None, None),
    # Bare UF codes — state preserved even without city
    ("MG", None, "MG"),
    ("SP", None, "SP"),
])
def test_normalize_location(raw, expected_city, expected_state):
    city, state = normalize_location(raw)
    assert city == expected_city
    assert state == expected_state
