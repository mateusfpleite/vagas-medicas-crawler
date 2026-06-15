from datetime import UTC, datetime

from vagas.spiders.gupy import GupySpider, _build_location, _parse_published_date


def _make_gupy_result(**overrides) -> dict:
    """Factory for a single Gupy API result dict."""
    base = {
        "id": 123456,
        "name": "Médico Clínico Geral",
        "jobUrl": "https://empresa.gupy.io/job/eyJqb2JJZCI6MTIzNDU2fQ==",
        "careerPageName": "Hospital São Lucas",
        "city": "São Paulo",
        "state": "São Paulo",
        "workplaceType": "on-site",
        "description": "Vaga para médico clínico geral em regime de plantão.",
        "publishedDate": "2025-08-17T20:31:08.667Z",
        "type": "vacancy_type_effective",
    }
    base.update(overrides)
    return base


def test_parse_results_basic():
    """All fields are mapped correctly from API dict to Vaga."""
    item = _make_gupy_result()
    vagas = GupySpider.parse_results([item])

    assert len(vagas) == 1
    v = vagas[0]
    assert v.title == "Médico Clínico Geral"
    assert v.location == "São Paulo, SP"
    assert v.source == "gupy"
    assert v.url == "https://empresa.gupy.io/job/eyJqb2JJZCI6MTIzNDU2fQ=="
    assert v.company == "Hospital São Lucas"
    assert v.external_id == "123456"
    assert v.description == "Vaga para médico clínico geral em regime de plantão."
    assert v.raw_html == v.description
    assert v.published_at is not None
    assert v.published_at.year == 2025
    assert v.published_at.month == 8
    assert v.published_at.day == 17
    assert v.job_type == "Presencial"


def test_parse_results_location_city_and_state():
    """City + state with full name produces 'City, UF' format."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(city="Rio de Janeiro", state="Rio de Janeiro"),
    ])
    assert vagas[0].location == "Rio de Janeiro, RJ"


def test_parse_results_location_city_only():
    """City without state uses city as location."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(city="Campinas", state=""),
    ])
    assert vagas[0].location == "Campinas"


def test_parse_results_location_state_only():
    """State without city uses UF abbreviation as location."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(city="", state="Minas Gerais"),
    ])
    assert vagas[0].location == "MG"


def test_parse_results_location_neither():
    """Missing city and state falls back to 'Brasil'."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(city="", state=""),
    ])
    assert vagas[0].location == "Brasil"


def test_parse_results_location_none_values():
    """None city and state falls back to 'Brasil'."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(city=None, state=None),
    ])
    assert vagas[0].location == "Brasil"


def test_parse_results_filters_non_medical():
    """Non-medical titles are excluded."""
    items = [
        _make_gupy_result(name="Enfermeiro Padrão", id=1),
        _make_gupy_result(name="Técnico de Enfermagem", id=2),
        _make_gupy_result(name="Médico Plantonista", id=3),
    ]
    vagas = GupySpider.parse_results(items)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico Plantonista"


def test_parse_results_filters_veterinary():
    """'Médico Veterinário' is excluded by is_medical_title."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(name="Médico Veterinário", id=1),
    ])
    assert len(vagas) == 0


def test_parse_results_filters_talent_pool():
    """Talent pool entries are excluded (not active job openings)."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(type="vacancy_type_talent_pool"),
    ])
    assert len(vagas) == 0


def test_parse_results_workplace_type_mapping():
    """workplaceType values are mapped to PT-BR."""
    for api_val, expected in [
        ("on-site", "Presencial"),
        ("remote", "Remoto"),
        ("hybrid", "Híbrido"),
    ]:
        vagas = GupySpider.parse_results([
            _make_gupy_result(workplaceType=api_val, id=hash(api_val)),
        ])
        assert vagas[0].job_type == expected, f"Failed for {api_val}"


def test_parse_results_workplace_type_unknown():
    """Unknown workplaceType maps to None."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(workplaceType="something-else"),
    ])
    assert vagas[0].job_type is None


def test_parse_results_published_date_parsing():
    """ISO 8601 with milliseconds and Z suffix is parsed correctly."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(publishedDate="2025-08-17T20:31:08.667Z"),
    ])
    dt = vagas[0].published_at
    assert dt is not None
    assert dt == datetime(2025, 8, 17, 20, 31, 8, 667000, tzinfo=UTC)


def test_parse_results_published_date_none():
    """Missing publishedDate results in None."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(publishedDate=None),
    ])
    assert vagas[0].published_at is None


def test_parse_results_empty_list():
    """Empty input returns empty output."""
    assert GupySpider.parse_results([]) == []


def test_parse_results_external_id_is_string():
    """Numeric id is converted to string."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(id=999),
    ])
    assert vagas[0].external_id == "999"
    assert isinstance(vagas[0].external_id, str)


def test_parse_results_description_stored_as_is():
    """Description is stored as plain text, not HTML-stripped."""
    text = "Vaga para médico com experiência em CTI. Regime 12x36."
    vagas = GupySpider.parse_results([
        _make_gupy_result(description=text),
    ])
    assert vagas[0].description == text
    assert vagas[0].raw_html == text


def test_parse_results_empty_title_skipped():
    """Items with empty title are skipped."""
    vagas = GupySpider.parse_results([
        _make_gupy_result(name=""),
    ])
    assert len(vagas) == 0


# --- Helper function tests ---


def test_build_location_all_states():
    """Spot-check a few state abbreviation mappings."""
    assert _build_location("Belo Horizonte", "Minas Gerais") == "Belo Horizonte, MG"
    assert _build_location("Curitiba", "Paraná") == "Curitiba, PR"
    assert _build_location("Manaus", "Amazonas") == "Manaus, AM"
    assert _build_location("Brasília", "Distrito Federal") == "Brasília, DF"


def test_parse_published_date_no_millis():
    """Dates without milliseconds are parsed correctly."""
    dt = _parse_published_date("2025-06-01T12:00:00Z")
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 6


def test_parse_published_date_empty_string():
    assert _parse_published_date("") is None


def test_parse_published_date_garbage():
    assert _parse_published_date("not-a-date") is None
