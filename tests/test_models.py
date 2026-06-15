from vagas.models import Vaga


def test_vaga_creation_minimal():
    v = Vaga(
        title="Médico Plantonista",
        location="São Paulo - SP",
        source="bne",
        url="https://example.com/vaga/123",
    )
    assert v.title == "Médico Plantonista"
    assert v.source == "bne"
    assert v.salary is None
    assert v.company is None


def test_vaga_creation_full():
    v = Vaga(
        title="Médico Clínico Geral",
        company="Hospital São Luiz",
        location="Rio de Janeiro - RJ",
        salary="R$ 120/hora",
        job_type="plantao",
        specialty="Clínica Médica",
        source="vagamedica",
        url="https://vagamedica.com.br/vaga/456",
        external_id="456",
        description="Plantão 12h em emergência",
    )
    assert v.company == "Hospital São Luiz"
    assert v.salary == "R$ 120/hora"
    assert v.external_id == "456"


def test_vaga_dedup_key():
    v = Vaga(
        title="Médico Plantonista",
        company="Hospital X",
        location="SP",
        source="bne",
        url="https://example.com/1",
    )
    key = v.dedup_key()
    assert isinstance(key, str)
    assert len(key) == 64  # SHA-256 hex digest


def test_vaga_same_dedup_key_different_sources():
    kwargs = dict(
        title="Médico Plantonista",
        company="Hospital X",
        location="São Paulo",
        source="bne",
        url="https://example.com/1",
    )
    v1 = Vaga(**kwargs)
    v2 = Vaga(**{**kwargs, "source": "indeed", "url": "https://other.com/2"})
    assert v1.dedup_key() == v2.dedup_key()


def test_vaga_dedup_key_normalizes_accents():
    v1 = Vaga(title="Médico", location="São Paulo - SP", source="a", url="http://a")
    v2 = Vaga(title="Medico", location="Sao Paulo - SP", source="b", url="http://b")
    assert v1.dedup_key() == v2.dedup_key()


def test_vaga_dedup_key_normalizes_punctuation():
    v1 = Vaga(title="Médico", location="São Paulo - SP", source="a", url="http://a")
    v2 = Vaga(title="Médico", location="São Paulo/SP", source="b", url="http://b")
    assert v1.dedup_key() == v2.dedup_key()


def test_vaga_new_fields_default_none():
    v = Vaga(title="Médico", location="SP", source="indeed", url="http://x")
    assert v.salary_min is None
    assert v.salary_max is None
    assert v.salary_period is None
    assert v.benefits is None


def test_vaga_new_fields_populated():
    v = Vaga(
        title="Médico",
        location="SP",
        source="indeed",
        url="http://x",
        salary_min=15000.0,
        salary_max=30000.0,
        salary_period="MONTHLY",
        benefits=["Assistência médica", "Vale-transporte"],
    )
    assert v.salary_min == 15000.0
    assert v.salary_max == 30000.0
    assert v.salary_period == "MONTHLY"
    assert v.benefits == ["Assistência médica", "Vale-transporte"]
