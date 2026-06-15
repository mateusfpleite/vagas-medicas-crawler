from pathlib import Path

from vagas.models import Vaga
from vagas.spiders.infojobs import InfoJobsSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_detail_extracts_jsonld():
    html = (FIXTURES / "infojobs_detail.html").read_text()
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico Ginecologista",
        location="Brasil",
        source="infojobs",
        url="https://www.infojobs.com.br/vaga-de-medico-ginecologista__11310399.aspx",
        external_id="11310399",
    )
    spider.parse_detail(html, vaga)

    assert vaga.company == "Santa Marcelina Saúde"
    assert vaga.location == "São Paulo, SP"
    assert vaga.job_type == "Jornada completa"
    assert "Ginecologista" in vaga.description
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 30
    assert vaga.raw_html == html


def test_parse_detail_no_jsonld():
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__123.aspx", external_id="123",
    )
    spider.parse_detail("<html><body><p>No data</p></body></html>", vaga)
    assert vaga.company is None
    assert vaga.description is None
    assert vaga.raw_html is not None


def test_parse_detail_empty_organization():
    html = '''<html><head><script type="application/ld+json">
    {"@type": "JobPosting", "title": "Médico", "description": "Desc"}
    </script></head><body></body></html>'''
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__456.aspx", external_id="456",
    )
    spider.parse_detail(html, vaga)
    assert vaga.company is None
    assert vaga.description == "Desc"


def test_parse_detail_multiple_jsonld_blocks():
    html = '''<html><head>
    <script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": []}
    </script>
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "Médico", "description": "Found it",
     "hiringOrganization": {"@type": "Organization", "name": "Hospital X"}}
    </script>
    </head><body></body></html>'''
    spider = InfoJobsSpider()
    vaga = Vaga(
        title="Médico", location="Brasil", source="infojobs",
        url="https://www.infojobs.com.br/vaga__789.aspx", external_id="789",
    )
    spider.parse_detail(html, vaga)
    assert vaga.description == "Found it"
    assert vaga.company == "Hospital X"


def test_parse_listing_extracts_vagas():
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico-clinico-geral-em-sao-paulo__11310001.aspx">
      <h2>Médico Clínico Geral</h2>
    </a>
    <a href="/vaga-de-medico-pediatra-em-curitiba__11310002.aspx">
      <h2>Médico Pediatra</h2>
    </a>
    <a href="/vaga-de-analista-financeiro-em-bh__11310003.aspx">
      <h2>Analista Financeiro</h2>
    </a>
    </body></html>"""

    vagas = spider.parse_listing(html)
    # "Analista Financeiro" is filtered out by allowlist (no "médic")
    assert len(vagas) == 2
    assert vagas[0].title == "Médico Clínico Geral"
    assert vagas[0].external_id == "11310001"
    assert vagas[0].url == "https://www.infojobs.com.br/vaga-de-medico-clinico-geral-em-sao-paulo__11310001.aspx"
    assert vagas[0].source == "infojobs"
    assert vagas[1].title == "Médico Pediatra"
    assert vagas[1].external_id == "11310002"


def test_parse_listing_filters_non_medical():
    """Three-layer filter: allowlist (must contain 'médic') + blocklist + scoring."""
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico-geral__1.aspx"><h2>Médico Clínico Geral</h2></a>
    <a href="/vaga-de-balconista__2.aspx"><h2>Balconista De Medicamentos</h2></a>
    <a href="/vaga-de-veterinario__3.aspx"><h2>Médico Veterinário</h2></a>
    <a href="/vaga-de-enfermeiro__4.aspx"><h2>Enfermeiro Intensivista</h2></a>
    <a href="/vaga-de-psiquiatra__5.aspx"><h2>Médico Psiquiatra</h2></a>
    <a href="/vaga-de-docente__6.aspx"><h2>Docente Medicina Veterinária</h2></a>
    <a href="/vaga-de-auxiliar__7.aspx"><h2>Auxiliar de Consultório Médico</h2></a>
    <a href="/vaga-de-secretaria__8.aspx"><h2>Secretária Clínica Médica</h2></a>
    <a href="/vaga-de-closer__9.aspx"><h2>Closer - Clínica Médica Estética</h2></a>
    <a href="/vaga-de-propagandista__10.aspx"><h2>PROPAGANDISTA MÉDICO JUNIOR</h2></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    titles = {v.title for v in vagas}
    assert "Médico Clínico Geral" in titles
    assert "Médico Psiquiatra" in titles
    # Existing filters catch these:
    assert "Balconista De Medicamentos" not in titles
    assert "Enfermeiro Intensivista" not in titles
    assert "Docente Medicina Veterinária" not in titles
    assert "Médico Veterinário" not in titles
    assert "Auxiliar de Consultório Médico" not in titles
    # NEW: scoring catches these (pass regex+blocklist but fail score):
    assert "Secretária Clínica Médica" not in titles
    assert "Closer - Clínica Médica Estética" not in titles
    assert "PROPAGANDISTA MÉDICO JUNIOR" not in titles


def test_parse_listing_empty():
    spider = InfoJobsSpider()
    vagas = spider.parse_listing("<html><body><p>No jobs</p></body></html>")
    assert vagas == []


def test_parse_listing_deduplicates_by_id():
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico__11310001.aspx"><h2>Médico A</h2></a>
    <a href="/vaga-de-medico-dup__11310001.aspx"><h2>Médico A Dup</h2></a>
    <a href="/vaga-de-medico-b__11310002.aspx"><h2>Médico B</h2></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    assert len(vagas) == 2
    ids = {v.external_id for v in vagas}
    assert ids == {"11310001", "11310002"}


def test_parse_listing_skips_no_id():
    """Links without __ID.aspx pattern should be skipped."""
    spider = InfoJobsSpider()
    html = """<html><body>
    <a href="/vaga-de-medico__12345.aspx"><h2>Médico Geral</h2></a>
    <a href="/sobre-nos.aspx"><h2>Sobre Nós</h2></a>
    </body></html>"""
    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico Geral"
