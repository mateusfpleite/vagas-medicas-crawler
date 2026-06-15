from pathlib import Path

import pytest

from vagas.spiders.trabalha_brasil import TrabalhaBrasilSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.skipif(
    not (FIXTURES / "trabalha_brasil_page.html").exists(),
    reason="Fixture not captured (anti-bot blocked)",
)
def test_parse_trabalha_brasil():
    html = (FIXTURES / "trabalha_brasil_page.html").read_text()
    spider = TrabalhaBrasilSpider()
    vagas = spider.parse(html)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.source == "trabalha_brasil"


@pytest.mark.skipif(
    not (FIXTURES / "trabalha_brasil_page.html").exists(),
    reason="Fixture not captured (anti-bot blocked)",
)
def test_parse_trabalha_brasil_has_location():
    html = (FIXTURES / "trabalha_brasil_page.html").read_text()
    spider = TrabalhaBrasilSpider()
    vagas = spider.parse(html)
    for v in vagas:
        assert v.location


def test_parse_empty_html():
    spider = TrabalhaBrasilSpider()
    vagas = spider.parse("<html><body></body></html>")
    assert vagas == []


def test_parse_basic_structure():
    html = """
    <html><body>
    <div class="job-item">
        <h2>Medico Clinico</h2>
        <span class="company">Hospital Z</span>
        <span class="location">Rio de Janeiro</span>
        <a href="/vaga/12345">Ver vaga</a>
    </div>
    </body></html>
    """
    spider = TrabalhaBrasilSpider()
    vagas = spider.parse(html)
    assert len(vagas) == 1
    assert vagas[0].title == "Medico Clinico"
    assert vagas[0].company == "Hospital Z"
    assert vagas[0].location == "Rio de Janeiro"
    assert vagas[0].url == "https://www.trabalhabrasil.com.br/vaga/12345"


def test_full_url_helper():
    spider = TrabalhaBrasilSpider()
    assert spider._full_url("") == ""
    assert spider._full_url("https://example.com") == "https://example.com"
    assert spider._full_url("/vaga/123") == "https://www.trabalhabrasil.com.br/vaga/123"
