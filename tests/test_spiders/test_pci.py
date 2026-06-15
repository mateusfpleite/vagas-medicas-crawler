from datetime import date

from vagas.models import Vaga
from vagas.spiders.pci import PCISpider, _parse_deadline


def test_parse_listing_extracts_cards():
    """All three card classes (da, na, ea) are captured."""

    spider = PCISpider()
    # da = highlighted/sponsored, na = normal/recent, ea = older entries
    html = """<html><body><div id="concursos">
<div class="da" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-lavras-mg-abre-169-vagas" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-lavras-mg-abre-169-vagas" title="Prefeitura de Lavras - MG abre 169 vagas" rel="bookmark" style="display:block;">Prefeitura de Lavras</a>
<div class="cb"><img src="data:image/png;base64,x" class="lazyload"></div>
<div class="cc">MG</div>
<div class="cd">169 vagas até R$ 5.286,42<br><span>Vários Cargos<br><span>Superior</span></span></div>
<div class="ce"><span>16/03 a<br>16/04/2026</span></div>
<div class="clear"></div></div></div>
<div class="na" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-vitorino-pr-abre-concurso" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-vitorino-pr-abre-concurso" title="Prefeitura de Vitorino - PR abre concurso" rel="bookmark" style="display:block;">Prefeitura de Vitorino</a>
<div class="cc">PR</div>
<div class="cd">64 vagas até R$ 20.945,34<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div>
<div class="ea" onclick="myClick(event)" data-url="https://www.pciconcursos.com.br/noticias/prefeitura-de-cardoso-sp-concurso" style="cursor:pointer;">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/prefeitura-de-cardoso-sp-concurso" title="Prefeitura de Cardoso - SP abre concurso" rel="bookmark" style="display:block;">Prefeitura de Cardoso</a>
<div class="cc">SP</div>
<div class="cd">62 vagas até R$ 7.602,95<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div>
</div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 3

    assert vagas[0].external_id == "prefeitura-de-lavras-mg-abre-169-vagas"
    assert vagas[0].company == "Prefeitura de Lavras"
    assert vagas[0].location == "MG"
    assert vagas[0].salary_max == 5286.42
    assert vagas[0].salary == "até R$ 5.286,42"
    assert vagas[0].source == "pci"

    assert vagas[1].external_id == "prefeitura-de-vitorino-pr-abre-concurso"
    assert vagas[1].location == "PR"
    assert vagas[1].salary_max == 20945.34

    assert vagas[2].external_id == "prefeitura-de-cardoso-sp-concurso"
    assert vagas[2].location == "SP"
    assert vagas[2].salary_max == 7602.95


def test_parse_listing_handles_cr_salary():
    """Salary with '+ CR' (cadastro reserva) is parsed correctly."""
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="na" data-url="https://www.pciconcursos.com.br/noticias/xaxim-sc">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/xaxim-sc" title="X" style="display:block;">Prefeitura de Xaxim</a>
<div class="cc">SC</div>
<div class="cd">5 vagas + CR até R$ 15.486,24<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div></div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].salary_max == 15486.24


def test_parse_listing_handles_cadastro_reserva_no_count():
    """'Cadastro reserva até R$ X' without vacancy count."""
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="ea" data-url="https://www.pciconcursos.com.br/noticias/tijucas-sc">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/tijucas-sc" title="X" style="display:block;">Prefeitura de Tijucas</a>
<div class="cc">SC</div>
<div class="cd">Cadastro reserva até R$ 21.773,73<br><span>Vários Cargos</span></div>
<div class="clear"></div></div></div></div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1
    assert vagas[0].salary_max == 21773.73


def test_parse_listing_deduplicates_by_slug():
    spider = PCISpider()
    html = """<html><body><div id="concursos">
<div class="na" data-url="https://www.pciconcursos.com.br/noticias/same-slug">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/same-slug" title="A" style="display:block;">A</a>
<div class="cc">SP</div><div class="cd">5 vagas até R$ 10.000,00</div>
<div class="clear"></div></div></div>
<div class="ea" data-url="https://www.pciconcursos.com.br/noticias/same-slug">
<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/same-slug" title="A dup" style="display:block;">A dup</a>
<div class="cc">SP</div><div class="cd">5 vagas até R$ 10.000,00</div>
<div class="clear"></div></div></div>
</div></body></html>"""

    vagas = spider.parse_listing(html)
    assert len(vagas) == 1


def test_parse_listing_empty_page():
    spider = PCISpider()
    vagas = spider.parse_listing("<html><body><div id='concursos'></div></body></html>")
    assert vagas == []


def test_parse_detail_extracts_jsonld_and_location():
    html = """<html><head>
<script type="application/ld+json" class="yoast-schema-graph">{"@context":"https://schema.org","@graph":[
{"@type":"NewsArticle","headline":"Prefeitura de Machado - MG abre Processo Seletivo",
 "datePublished":"2026-01-12T19:12:56-03:00","dateModified":"2026-01-12T19:12:56-03:00",
 "publisher":{"@id":"https://www.pciconcursos.com.br/#organization"}},
{"@type":"Organization","name":"PCI Concursos"}
]}</script></head><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Machado - MG abre Processo Seletivo para Médico Clínico Geral</h1>
<abbr class="published" title="2026-01-12T19:12:56-03:00">12 de janeiro de 2026</abbr>
<div itemprop="articleBody">
<p>A Prefeitura de Machado anunciou abertura do Processo Seletivo.</p>
<ul><li>Médico Clínico Geral (1 vaga)</li></ul>
<p>A remuneração mensal é de R$ 14.746,36.</p>
</div></article>
<aside id="links"><ul>
<li class="pdf"><a href="https://arq.pciconcursos.com.br/edital.pdf" title="EDITAL">EDITAL DE ABERTURA</a></li>
</ul></aside></body></html>"""

    vaga = Vaga(
        title="Prefeitura de Machado",
        location="MG",
        source="pci",
        url="https://www.pciconcursos.com.br/noticias/prefeitura-de-machado-mg",
        external_id="prefeitura-de-machado-mg",
    )
    result = PCISpider.parse_detail(html, vaga)

    assert result is True
    assert vaga.published_at is not None
    assert vaga.published_at.year == 2026
    assert vaga.published_at.month == 1
    assert vaga.published_at.day == 12
    assert vaga.location == "Machado, MG"
    assert vaga.description is not None
    assert "R$ 14.746,36" in vaga.description
    assert vaga.raw_html == html


def test_parse_detail_multi_position_with_medical():
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Vitorino - PR abre concurso</h1>
<abbr class="published" title="2026-02-02T17:39:06-03:00">2 de fevereiro de 2026</abbr>
<div itemprop="articleBody">
<p>Vagas para diversos cargos:</p>
<ul>
<li>Agente de Saúde (5 vagas)</li>
<li>Enfermeiro II</li>
<li>Médico Clínico Geral II</li>
<li>Médico Ginecologista e Obstetra</li>
<li>Médico Pediatra</li>
<li>Médico Veterinário (1 vaga)</li>
<li>Psicólogo</li>
</ul>
<p>Remuneração de R$ 1.669,91 a R$ 20.945,34 mensais.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Prefeitura de Vitorino",
        location="PR",
        source="pci",
        url="https://www.pciconcursos.com.br/noticias/test",
        external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)

    assert result is True
    assert vaga.location == "Vitorino, PR"
    assert vaga.description is not None
    assert vaga.published_at is not None


def test_parse_detail_only_veterinary_returns_false():
    """Médico Veterinário without human doctor positions is rejected."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Teste - SP abre concurso</h1>
<div itemprop="articleBody">
<p>Vagas:</p>
<ul>
<li>Médico Veterinário (2 vagas)</li>
<li>Auxiliar Administrativo (3 vagas)</li>
</ul>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False


def test_parse_detail_no_medical_positions_returns_false():
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Teste - SP abre concurso</h1>
<div itemprop="articleBody">
<p>Vagas para cargos administrativos:</p>
<ul>
<li>Auxiliar Administrativo (3 vagas)</li>
<li>Motorista (2 vagas)</li>
</ul>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False
    # Description must NOT be set when returning False (filter depends on this)
    assert vaga.description is None


def test_parse_detail_no_article_body_returns_false():
    html = "<html><body><h1>Empty page</h1></body></html>"
    vaga = Vaga(
        title="Test", location="SP", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is False


def test_parse_detail_fallback_to_abbr_date():
    """When JSON-LD is missing, falls back to abbr.published."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Prefeitura de Ipê - RS abre processo</h1>
<abbr class="published" title="2026-01-28T16:16:16-03:00">28 de janeiro de 2026</abbr>
<div itemprop="articleBody">
<p>Vagas para Médico PSF.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="RS", source="pci",
        url="https://test.com", external_id="test",
    )
    result = PCISpider.parse_detail(html, vaga)
    assert result is True
    assert vaga.published_at is not None
    assert vaga.published_at.day == 28
    assert vaga.location == "Ipê, RS"


def test_parse_detail_location_hospital():
    """Location extracted from hospital headlines."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">Hospital Beneficente Dr. César Santos de Passo Fundo - RS abre processo</h1>
<div itemprop="articleBody">
<p>Vagas para Médico Plantonista.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="RS", source="pci",
        url="https://test.com", external_id="test",
    )
    PCISpider.parse_detail(html, vaga)
    assert vaga.location == "Passo Fundo, RS"


def test_parse_detail_location_no_state_keeps_original():
    """Headlines without '- UF' pattern keep listing state."""
    html = """<html><body>
<article id="noticia">
<h1 itemprop="headline">AgSUS reabre Processo Seletivo com diversas oportunidades</h1>
<div itemprop="articleBody">
<p>Vagas para Médico em todo o Brasil.</p>
</div></article></body></html>"""

    vaga = Vaga(
        title="Test", location="Brasil", source="pci",
        url="https://test.com", external_id="test",
    )
    PCISpider.parse_detail(html, vaga)
    assert vaga.location == "Brasil"  # unchanged


# --- _parse_deadline tests ---


def test_parse_deadline_single_date():
    assert _parse_deadline("05/03/2026") == date(2026, 3, 5)


def test_parse_deadline_range():
    assert _parse_deadline("23/03 a 22/04/2026") == date(2026, 4, 22)


def test_parse_deadline_reaberto_prefix():
    assert _parse_deadline("Reaberto até 12/02/2026") == date(2026, 2, 12)


def test_parse_deadline_prorrogado_prefix():
    assert _parse_deadline("Prorrogado até 30/03/2026") == date(2026, 3, 30)


def test_parse_deadline_no_date():
    assert _parse_deadline("Sem data") is None


def test_parse_deadline_empty():
    assert _parse_deadline("") is None


# --- Freshness filter in parse_listing ---


def _make_card(slug: str, state: str, deadline: str | None = None) -> str:
    ce = f'<div class="ce"><span>{deadline}</span></div>' if deadline else ""
    return (
        f'<div class="na" data-url="https://www.pciconcursos.com.br/noticias/{slug}">'
        f'<div class="ca"><a href="https://www.pciconcursos.com.br/noticias/{slug}" '
        f'title="Test {slug}" style="display:block;">Test</a>'
        f'<div class="cc">{state}</div>'
        f'<div class="cd">5 vagas até R$ 10.000,00</div>'
        f'{ce}'
        f'<div class="clear"></div></div></div>'
    )


def test_parse_listing_filters_expired_cards():
    html = f"""<html><body><div id="concursos">
    {_make_card("open-vaga", "SP", "15/03/2026")}
    {_make_card("expired-vaga", "MG", "01/01/2025")}
    </div></body></html>"""

    spider = PCISpider()
    vagas = spider.parse_listing(html, today=date(2026, 2, 7))

    assert len(vagas) == 1
    assert vagas[0].external_id == "open-vaga"


def test_parse_listing_keeps_card_without_deadline():
    """Cards without div.ce are kept (fail-open)."""
    html = f"""<html><body><div id="concursos">
    {_make_card("no-date-vaga", "RJ")}
    </div></body></html>"""

    spider = PCISpider()
    vagas = spider.parse_listing(html, today=date(2026, 2, 7))

    assert len(vagas) == 1
    assert vagas[0].external_id == "no-date-vaga"


def test_parse_listing_keeps_card_with_today_deadline():
    """Card whose deadline is exactly today is still shown."""
    html = f"""<html><body><div id="concursos">
    {_make_card("today-vaga", "PR", "07/02/2026")}
    </div></body></html>"""

    spider = PCISpider()
    vagas = spider.parse_listing(html, today=date(2026, 2, 7))

    assert len(vagas) == 1
