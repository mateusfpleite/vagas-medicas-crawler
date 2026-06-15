import json
from pathlib import Path

from vagas.spiders.bne import BNESpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_bne_response():
    raw = json.loads((FIXTURES / "bne_response.json").read_text())
    spider = BNESpider()
    vagas = spider.parse(raw)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.location
        assert v.source == "bne"
        assert v.url.startswith("http")


def test_parse_empty_response():
    spider = BNESpider()
    vagas = spider.parse({"success": True, "data": {"listVagas": []}})
    assert vagas == []


def test_parse_missing_data_key():
    spider = BNESpider()
    vagas = spider.parse({"success": True})
    assert vagas == []


def test_parse_skips_items_without_title():
    raw = {
        "success": True,
        "data": {
            "listVagas": [
                {
                    "Idf_Vaga": 123,
                    "Title": "",
                    "City": "SP",
                    "State": "SP",
                    "UrlJob": "/vaga/123",
                },
                {
                    "Idf_Vaga": 456,
                    "Title": "Médico",
                    "City": "RJ",
                    "State": "RJ",
                    "UrlJob": "/vaga/456",
                },
            ]
        },
    }
    spider = BNESpider()
    vagas = spider.parse(raw)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico"


def test_vaga_fields_from_fixture():
    raw = json.loads((FIXTURES / "bne_response.json").read_text())
    spider = BNESpider()
    vagas = spider.parse(raw)
    first = vagas[0]
    assert first.external_id is not None
    assert "/" in first.location  # "City/State"
    assert first.specialty  # Area field


def test_parse_date_iso():
    """ISO date string should be parsed."""
    dt = BNESpider._parse_date({"DateInsert": "2026-01-20T14:30:00"})
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 1
    assert dt.day == 20


def test_parse_date_dotnet():
    """.NET /Date(epoch)/ format should be parsed."""
    # 2026-01-15 00:00:00 UTC = 1768435200000 ms
    dt = BNESpider._parse_date({"DateInsert": "/Date(1768435200000)/"})
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 1


def test_parse_date_epoch_ms():
    """Epoch milliseconds should be parsed."""
    dt = BNESpider._parse_date({"DateInsert": 1768435200000})
    assert dt is not None
    assert dt.year == 2026


def test_parse_date_missing():
    """No date fields should return None."""
    dt = BNESpider._parse_date({"Title": "Médico"})
    assert dt is None


# --- parse_detail tests ---------------------------------------------------

def _make_detail_html(empresa="Hospital ABC", salario="R$ 15.000",
                      modalidade="Presencial", contrato="Efetivo",
                      descricao="Vaga para cardiologista em regime CLT."):
    return f"""<html><body><main>
<h1>Vaga de Médico</h1>
<p>Cargo: Médico</p>
<p>Salário: {salario}</p>
<p>Empresa: {empresa}</p>
<p>Local: Cuiabá</p>
<p>Modalidade: {modalidade}</p>
<p>Contrato: {contrato}</p>
<h2>Descrição Geral</h2>
<p>{descricao}</p>
</main></body></html>"""


def _make_vaga():
    from vagas.models import Vaga
    return Vaga(
        title="Médico",
        location="Cuiabá/MT",
        source="bne",
        url="https://www.bne.com.br/vaga/123",
        external_id="123",
    )


def test_parse_detail_extracts_company():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert vaga.company == "Hospital ABC"


def test_parse_detail_extracts_salary():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert vaga.salary == "R$ 15.000"


def test_parse_detail_extracts_job_type():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert "Presencial" in vaga.job_type
    assert "Efetivo" in vaga.job_type


def test_parse_detail_extracts_description():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert "cardiologista" in vaga.description


def test_parse_detail_stores_raw_html():
    vaga = _make_vaga()
    html = _make_detail_html()
    BNESpider.parse_detail(html, vaga)
    assert vaga.raw_html == html


def test_parse_detail_skips_a_combinar_salary():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(salario="A combinar"), vaga)
    assert vaga.salary is None


def test_parse_detail_skips_confidencial_company():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(empresa="Confidencial"), vaga)
    assert vaga.company is None


def test_parse_detail_skips_sine_description():
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(descricao="sine"), vaga)
    assert vaga.description is None


def test_parse_detail_no_main_tag():
    vaga = _make_vaga()
    BNESpider.parse_detail("<html><body><p>No main</p></body></html>", vaga)
    assert vaga.company is None
    assert vaga.description is None
    assert vaga.raw_html is not None  # still stored for debugging


# --- _extract_jsonld tests -------------------------------------------------

def test_extract_jsonld_returns_parsed_dict():
    html = (FIXTURES / "bne_detail.html").read_text()
    data = BNESpider._extract_jsonld(html)
    assert data is not None
    assert data["@type"] == "JobPosting"
    assert data["hiringOrganization"]["name"] == "Hospital Santa Casa"


def test_extract_jsonld_returns_none_without_script():
    data = BNESpider._extract_jsonld("<html><body>no json-ld</body></html>")
    assert data is None


def test_extract_jsonld_returns_none_on_bad_json():
    html = '<html><script type="application/ld+json">{ bad json</script></html>'
    data = BNESpider._extract_jsonld(html)
    assert data is None


def test_extract_jsonld_skips_non_jobposting_blocks():
    """When multiple JSON-LD blocks exist, only JobPosting is returned."""
    html = """<html><head>
    <script type="application/ld+json">{"@type": "BreadcrumbList", "name": "nav"}</script>
    <script type="application/ld+json">{"@type": "JobPosting", "hiringOrganization": {"name": "TestCo"}}</script>
    </head></html>"""
    data = BNESpider._extract_jsonld(html)
    assert data is not None
    assert data["@type"] == "JobPosting"
    assert data["hiringOrganization"]["name"] == "TestCo"


def test_parse_detail_extracts_company_from_jsonld():
    """JSON-LD hiringOrganization.name is preferred for company."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.company == "Hospital Santa Casa"


def test_parse_detail_extracts_published_at_from_jsonld():
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 20


def test_parse_detail_description_excludes_ui_junk():
    """Description should NOT contain 'Candidatar-me', 'Compartilhe', 'Plano VIP'."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert vaga.description is not None
    assert "Candidatar-me" not in vaga.description
    assert "Compartilhe" not in vaga.description
    assert "Plano VIP" not in vaga.description
    assert "Candidaturas ilimitadas" not in vaga.description


def test_parse_detail_description_has_real_content():
    """Description should contain the actual job content."""
    html = (FIXTURES / "bne_detail.html").read_text()
    vaga = _make_vaga()
    BNESpider.parse_detail(html, vaga)
    assert "exames admissionais" in vaga.description
    assert "PCMSO" in vaga.description


def test_parse_detail_falls_back_to_html_without_jsonld():
    """Without JSON-LD, parse_detail still works from HTML."""
    vaga = _make_vaga()
    BNESpider.parse_detail(_make_detail_html(), vaga)
    assert vaga.company == "Hospital ABC"
    assert "cardiologista" in vaga.description


def test_parse_filters_non_doctor_by_scoring():
    """Scoring filter catches non-doctor titles in BNE API results."""
    raw = {
        "success": True,
        "data": {
            "listVagas": [
                {
                    "Idf_Vaga": 100,
                    "Title": "Secretária Clínica Médica",
                    "City": "SP",
                    "State": "SP",
                    "UrlJob": "/vaga/100",
                },
                {
                    "Idf_Vaga": 200,
                    "Title": "Médico Cardiologista",
                    "City": "RJ",
                    "State": "RJ",
                    "UrlJob": "/vaga/200",
                },
                {
                    "Idf_Vaga": 300,
                    "Title": "PROPAGANDISTA MÉDICO JUNIOR",
                    "City": "MG",
                    "State": "MG",
                    "UrlJob": "/vaga/300",
                },
            ]
        },
    }
    spider = BNESpider()
    vagas = spider.parse(raw)
    titles = {v.title for v in vagas}
    assert "Médico Cardiologista" in titles
    assert "Secretária Clínica Médica" not in titles
    assert "PROPAGANDISTA MÉDICO JUNIOR" not in titles
