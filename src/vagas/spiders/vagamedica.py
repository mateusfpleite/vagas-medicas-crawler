import logging

import httpx
from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.models import Vaga

log = logging.getLogger(__name__)


class VagaMedicaSpider(BaseSpider):
    """
    Spider para o site VagaMédica (vagamedica.com.br).

    O site é HTML estático com cards de vagas.
    Estrutura: .jb-card > .jb-role (título), .jb-location, .jb-salary, .jb-btn (link).
    Links geralmente apontam para WhatsApp (wa.me).
    """

    name = "vagamedica"
    BASE_URL = "https://vagamedica.com.br"

    def parse(self, html: str) -> list[Vaga]:
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []

        for card in soup.select(".jb-card"):
            role_el = card.select_one(".jb-role")
            title = role_el.get_text(strip=True) if role_el else ""
            if not title:
                continue

            loc_el = card.select_one(".jb-location")
            location = loc_el.get_text(strip=True) if loc_el else ""
            # Remove emoji prefix (📍 )
            location = location.lstrip("\U0001f4cd").strip()

            sal_el = card.select_one(".jb-salary")
            salary = sal_el.get_text(strip=True) if sal_el else None

            btn_el = card.select_one(".jb-btn")
            href = btn_el.get("href", "") if btn_el else ""
            url = self._full_url(href)

            # Extract description from the details list items
            detail_items = card.select(".jb-list li")
            description = " | ".join(
                li.get_text(strip=True) for li in detail_items
            ) or None

            vagas.append(
                Vaga(
                    title=title,
                    location=location or "Brasil",
                    source=self.name,
                    url=url,
                    salary=salary,
                    description=description,
                )
            )

        log.info("VagaMédica parse: %d vagas", len(vagas))
        return vagas

    def _full_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith(("http", "wa.me")):
            return href if href.startswith("http") else f"https://{href}"
        return f"{self.BASE_URL}{href}"

    async def crawl(self) -> list[Vaga]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.BASE_URL, follow_redirects=True)
            resp.raise_for_status()
            return self.parse(resp.text)
