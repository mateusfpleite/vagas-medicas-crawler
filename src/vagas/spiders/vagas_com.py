import asyncio
import logging
import random
import re
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_page
from vagas.models import Vaga
from vagas.scoring import medical_score, TITLE_THRESHOLD

log = logging.getLogger(__name__)

# Title keywords that indicate a non-medical job
_TITLE_EXCLUDE_RE = re.compile(
    r"\b(est[áa]gio|balconista|ensino\s+m[ée]dio|vendedor|auxiliar|t[ée]cnico)\b",
    re.IGNORECASE,
)

# Title must contain a medical keyword to be accepted
_TITLE_MEDICAL_RE = re.compile(
    r"\bm[ée]dic[oa]?\b",
    re.IGNORECASE,
)


class VagasComSpider(BaseSpider):
    """
    Spider para o Vagas.com.br.

    Usa Playwright + stealth para renderizar a pagina.
    Vagas.com tem Cloudflare; pode bloquear.

    Estrutura dos cards:
      li.vaga                     - container
        .cargo a                  - titulo + link
        .emprVaga                 - empresa
        .vaga-local               - localidade (texto direto, ignorando tooltip)
        .detalhes p               - descricao resumida
        .nivelVaga                - nivel da vaga (job_type)
        a[data-id-vaga]           - id externo
    """

    name = "vagas_com"
    WAIT_SELECTOR = "li.vaga"
    BASE_URL = "https://www.vagas.com.br"
    LOAD_MORE_SELECTOR = 'a.btMaisVagas'
    MAX_LOAD_MORE = 10  # click "mostrar mais" up to N times

    _SEARCH_URLS = [
        "https://www.vagas.com.br/vagas-de-medico",
        "https://www.vagas.com.br/vagas-de-medico-plantonista",
        "https://www.vagas.com.br/vagas-de-medico-do-trabalho",
        "https://www.vagas.com.br/vagas-de-medico-clinico-geral",
        "https://www.vagas.com.br/vagas-de-medico-pediatra",
        "https://www.vagas.com.br/vagas-de-medico-ginecologista",
        "https://www.vagas.com.br/vagas-de-medico-psiquiatra",
        "https://www.vagas.com.br/vagas-de-medico-cirurgiao",
    ]

    def parse(self, html: str) -> list[Vaga]:
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []

        for card in soup.select("li.vaga"):
            # Title -- remove <mark> tags to avoid word-joining
            cargo_el = card.select_one(".cargo a")
            if not cargo_el:
                continue
            # Replace <mark> tags with their text + space to avoid word-joining
            for mark in cargo_el.find_all("mark"):
                mark.replace_with(f" {mark.get_text()} ")
            title = cargo_el.get_text(separator=" ", strip=True)
            title = re.sub(r"\s+", " ", title)
            if not title:
                continue

            # Three-layer filter: allowlist + blocklist + scoring
            if not _TITLE_MEDICAL_RE.search(title):
                continue
            if _TITLE_EXCLUDE_RE.search(title):
                continue
            if medical_score(title) < TITLE_THRESHOLD:
                continue

            # URL
            href = cargo_el.get("href", "")
            url = self._full_url(href)

            # External ID
            external_id = cargo_el.get("data-id-vaga")

            # Company
            company_el = card.select_one(".emprVaga")
            company = company_el.get_text(strip=True) if company_el else None

            # Location -- extract text from .vaga-local, excluding tooltip
            location = self._extract_location(card)

            # Description
            desc_el = card.select_one(".detalhes p")
            if desc_el:
                for mark in desc_el.find_all("mark"):
                    mark.replace_with(f" {mark.get_text()} ")
                description = desc_el.get_text(separator=" ", strip=True)
                description = re.sub(r"\s+", " ", description) or None
            else:
                description = None

            # Job type / level
            nivel_el = card.select_one(".nivelVaga")
            job_type = nivel_el.get_text(strip=True) if nivel_el else None

            vagas.append(
                Vaga(
                    title=title,
                    location=location or "Brasil",
                    source=self.name,
                    url=url,
                    company=company,
                    description=description,
                    job_type=job_type,
                    external_id=external_id,
                )
            )

        log.info("Vagas.com parse: %d vagas", len(vagas))
        return vagas

    def _extract_location(self, card) -> str:
        loc_el = card.select_one(".vaga-local")
        if not loc_el:
            return ""
        # Remove tooltip sub-elements before extracting text
        for tooltip in loc_el.select(".tooltip-place"):
            tooltip.decompose()
        # Remove icon elements
        for icon in loc_el.select("i"):
            icon.decompose()
        text = loc_el.get_text(strip=True)
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _extract_published_at(html: str) -> datetime | None:
        """Extract publication date from detail page HTML."""
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one("li.job-breadcrumb__item--published")
        if not el:
            return None
        text = el.get_text(strip=True)
        # "Publicada em DD/MM/YYYY"
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
        if m:
            try:
                return datetime(
                    int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=UTC,
                )
            except ValueError:
                return None
        # "Publicada há N dias"
        m = re.search(r"há\s+(\d+)\s+dia", text)
        if m:
            return datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0,
            ) - timedelta(days=int(m.group(1)))
        return None

    def _full_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("http"):
            return href
        return f"{self.BASE_URL}{href}"

    async def _load_listing(self, page, url: str) -> str:
        """Load a listing page and click 'mostrar mais' to expand results."""
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(self.WAIT_SELECTOR, timeout=20000)
        except Exception:
            log.warning("[%s] blocked or failed for %s", self.name, url)
            return ""

        # Click "mostrar mais vagas" to load additional results
        for i in range(self.MAX_LOAD_MORE):
            btn = page.locator(self.LOAD_MORE_SELECTOR)
            if not await btn.count():
                break
            try:
                await btn.click()
                await asyncio.sleep(random.uniform(1.5, 3))
                log.debug("[%s] load-more click %d on %s", self.name, i + 1, url)
            except Exception:
                break

        return await page.content()

    async def crawl(self, known_ids: set[str] | None = None, locations: list[str] | None = None) -> list[Vaga]:
        seen_ids: set[str] = set()
        all_vagas: list[Vaga] = []

        for url in self._SEARCH_URLS:
            async with stealth_page(proxy=self._proxy) as page:
                html = await self._load_listing(page, url)

            if not html and self._record_failure():
                # Proxy just activated — retry this URL with proxy
                log.info("[%s] proxy activated, retrying %s", self.name, url)
                async with stealth_page(proxy=self._proxy) as page:
                    html = await self._load_listing(page, url)

            if not html:
                continue

            self._record_success()
            vagas = self.parse(html)
            new = 0
            for v in vagas:
                eid = v.external_id or v.url
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    all_vagas.append(v)
                    new += 1

            log.info("[%s] %s: %d vagas (%d new)", self.name, url.split("/")[-1], len(vagas), new)
            await asyncio.sleep(random.uniform(2, 4))

        if not all_vagas:
            return []

        log.info("[%s] total unique from listings: %d", self.name, len(all_vagas))

        _known = known_ids or set()
        need_detail = [v for v in all_vagas if v.url and v.external_id not in _known]
        log.info("[%s] %d vagas need detail (%d already known)",
                 self.name, len(need_detail), len(all_vagas) - len(need_detail))

        fetched = 0
        async with stealth_page(proxy=self._proxy) as page:
            for vaga in need_detail:
                try:
                    await page.goto(vaga.url, wait_until="domcontentloaded")
                    await asyncio.sleep(1)
                    vaga.raw_html = await page.content()
                    vaga.published_at = self._extract_published_at(vaga.raw_html)
                    fetched += 1
                    self._record_success()
                    log.debug("[%s] Fetched detail: %s", self.name, vaga.url)
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] Failed to fetch detail %s: %s", self.name, vaga.url, e)
        log.info("[%s] Fetched details: %d/%d", self.name, fetched, len(need_detail))

        return all_vagas
