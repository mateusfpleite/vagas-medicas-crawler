import logging

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import fetch_rendered_html
from vagas.models import Vaga

log = logging.getLogger(__name__)


class TrabalhaBrasilSpider(BaseSpider):
    """
    Spider para o Trabalha Brasil (trabalhabrasil.com.br).

    O site usa reCAPTCHA v3 e frequentemente bloqueia scrapers.
    Este spider e best-effort: se bloqueado, crawl() retorna [].

    Estrutura esperada (quando acessivel):
      .job-item ou similar card container
        titulo, empresa, localidade, link
    """

    name = "trabalha_brasil"
    SEARCH_URL = "https://www.trabalhabrasil.com.br/vagas-emprego/medico"
    WAIT_SELECTOR = ".job-item"

    def parse(self, html: str) -> list[Vaga]:
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []

        # Best-effort selectors -- site is typically blocked by reCAPTCHA.
        # If HTML was captured, attempt extraction with common patterns.
        for card in soup.select(".job-item"):
            title_el = card.select_one("h2, .job-title, .title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            company_el = card.select_one(".company, .empresa")
            company = company_el.get_text(strip=True) if company_el else None

            loc_el = card.select_one(".location, .local")
            location = loc_el.get_text(strip=True) if loc_el else "Brasil"

            link_el = card.select_one("a[href]")
            href = link_el.get("href", "") if link_el else ""
            url = self._full_url(href)

            vagas.append(
                Vaga(
                    title=title,
                    location=location,
                    source=self.name,
                    url=url,
                    company=company,
                )
            )

        log.info("Trabalha Brasil parse: %d vagas", len(vagas))
        return vagas

    def _full_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        return f"https://www.trabalhabrasil.com.br{href}"

    async def crawl(self) -> list[Vaga]:
        html = await fetch_rendered_html(
            self.SEARCH_URL, self.WAIT_SELECTOR, timeout=20000
        )
        if not html:
            log.warning("%s blocked or failed -- skipping", self.name)
            return []
        return self.parse(html)
