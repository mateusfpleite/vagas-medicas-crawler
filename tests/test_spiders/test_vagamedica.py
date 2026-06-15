from pathlib import Path

from vagas.spiders.vagamedica import VagaMedicaSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_vagamedica():
    html = (FIXTURES / "vagamedica_page.html").read_text()
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.source == "vagamedica"
        assert v.url  # pode ser wa.me ou link web


def test_parse_returns_location():
    html = (FIXTURES / "vagamedica_page.html").read_text()
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    for v in vagas:
        assert v.location
        # Location should not contain the pin emoji
        assert "\U0001f4cd" not in v.location


def test_parse_extracts_salary_when_present():
    html = (FIXTURES / "vagamedica_page.html").read_text()
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    # At least some cards have salary info
    with_salary = [v for v in vagas if v.salary]
    assert len(with_salary) > 0
    for v in with_salary:
        assert "R$" in v.salary or "Combinar" in v.salary


def test_parse_whatsapp_urls():
    html = (FIXTURES / "vagamedica_page.html").read_text()
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    wa_vagas = [v for v in vagas if "wa.me" in v.url]
    assert len(wa_vagas) > 0
    for v in wa_vagas:
        assert v.url.startswith("https://wa.me")


def test_parse_empty_html():
    spider = VagaMedicaSpider()
    vagas = spider.parse("<html><body></body></html>")
    assert vagas == []


def test_parse_skips_cards_without_title():
    html = """
    <html><body>
    <div class="jb-card">
        <h3 class="jb-role"></h3>
        <span class="jb-location">SP</span>
        <a class="jb-btn" href="https://wa.me/123"></a>
    </div>
    <div class="jb-card">
        <h3 class="jb-role">Médico</h3>
        <span class="jb-location">RJ</span>
        <a class="jb-btn" href="https://wa.me/456"></a>
    </div>
    </body></html>
    """
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    assert len(vagas) == 1
    assert vagas[0].title == "Médico"


def test_full_url_helper():
    spider = VagaMedicaSpider()
    assert spider._full_url("") == ""
    assert spider._full_url("https://wa.me/123") == "https://wa.me/123"
    assert spider._full_url("wa.me/123") == "https://wa.me/123"
    assert spider._full_url("/vaga/1") == "https://vagamedica.com.br/vaga/1"
    assert spider._full_url("https://example.com") == "https://example.com"
