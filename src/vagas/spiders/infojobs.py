import asyncio
import json
import logging
import random
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_page
from vagas.filters import is_medical_title
from vagas.models import Vaga
from vagas.scoring import medical_score, TITLE_THRESHOLD

log = logging.getLogger(__name__)

BASE_URL = "https://www.infojobs.com.br"

# Extract numeric job ID from URL: __11310399.aspx -> 11310399
_ID_RE = re.compile(r"__(\d+)\.aspx")

# Title must contain "médic" to be considered a doctor vacancy
_TITLE_MEDICAL_RE = re.compile(r"\bm[ée]dic[oa]?\b", re.IGNORECASE)


class InfoJobsSpider(BaseSpider):
    """
    Spider para o InfoJobs Brasil (infojobs.com.br).

    Listing: Playwright com queries de busca por especialidade.
    Detail: httpx GET + JSON-LD parsing.
    """

    name = "infojobs"
    WAIT_SELECTOR = 'a[href*="/vaga-de-"]'

    _SEARCH_QUERIES = [
        "médico",
        "médico clínico geral",
        "médico plantonista",
        "médico do trabalho",
        "médico pediatra",
        "médico ginecologista",
        "médico cardiologista",
        "médico ortopedista",
        "médico psiquiatra",
        "médico cirurgião",
        "médico intensivista",
        "médico anestesista",
        "médico dermatologista",
        "médico neurologista",
        "médico oftalmologista",
        "médico endocrinologista",
    ]

    async def crawl(self, known_ids: set[str] | None = None, locations: list[str] | None = None) -> list[Vaga]:
        seen_ids: set[str] = set()
        all_vagas: list[Vaga] = []

        for query in self._SEARCH_QUERIES:
            url = f"{BASE_URL}/empregos.aspx?palabra={quote_plus(query)}"
            async with stealth_page(proxy=self._proxy) as page:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_selector(self.WAIT_SELECTOR, timeout=15000)
                    await asyncio.sleep(2)
                except Exception:
                    self._record_failure()
                    log.warning("[%s] failed/blocked for query '%s'", self.name, query)
                    continue

                self._record_success()
                html = await page.content()
                vagas = self.parse_listing(html)

                new = 0
                for v in vagas:
                    if v.external_id and v.external_id not in seen_ids:
                        seen_ids.add(v.external_id)
                        all_vagas.append(v)
                        new += 1

                log.info("[%s] query '%s': %d results (%d new)",
                         self.name, query, len(vagas), new)

            await asyncio.sleep(2 + random.uniform(0.5, 1.5))

        log.info("[%s] total unique from listings: %d", self.name, len(all_vagas))

        _known = known_ids or set()
        need_detail = [v for v in all_vagas if v.external_id not in _known]
        log.info("[%s] %d vagas need detail (%d already known)",
                 self.name, len(need_detail), len(all_vagas) - len(need_detail))

        fetched = 0
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
            follow_redirects=True,
            timeout=15.0,
            proxy=self._proxy,
        ) as client:
            for vaga in need_detail:
                try:
                    resp = await client.get(vaga.url)
                    if resp.status_code == 200:
                        self.parse_detail(resp.text, vaga)
                        fetched += 1
                        self._record_success()
                    else:
                        self._record_failure()
                        log.warning("[%s] detail %s returned %d",
                                    self.name, vaga.url, resp.status_code)
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] detail failed %s: %s", self.name, vaga.url, e)

                await asyncio.sleep(1 + random.uniform(0.5, 1.0))

        log.info("[%s] details fetched: %d/%d", self.name, fetched, len(need_detail))
        log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
        return all_vagas

    def parse_listing(self, html: str) -> list[Vaga]:
        """Extract job cards from a listing page, filtering non-medical titles."""
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []
        seen_ids: set[str] = set()

        for link in soup.select('a[href*="/vaga-de-"]'):
            href = link.get("href", "")
            m = _ID_RE.search(href)
            if not m:
                continue

            job_id = m.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title_el = link.select_one("h2, h3")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Three-layer filter: allowlist + blocklist + scoring (avoid detail fetches for non-doctors)
            if not _TITLE_MEDICAL_RE.search(title):
                continue
            if not is_medical_title(title):
                continue
            if medical_score(title) < TITLE_THRESHOLD:
                continue

            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            vagas.append(Vaga(
                title=title,
                location="Brasil",
                source=self.name,
                url=url,
                external_id=job_id,
            ))

        return vagas

    @staticmethod
    def parse_detail(html: str, vaga: Vaga) -> None:
        """Enrich a Vaga in-place with JSON-LD data from the detail page."""
        vaga.raw_html = html
        soup = BeautifulSoup(html, "lxml")

        # Find JobPosting JSON-LD (may have multiple blocks: BreadcrumbList, etc.)
        data = None
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            if not ld_tag.string:
                continue
            try:
                parsed = json.loads(ld_tag.string)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("@type") == "JobPosting":
                data = parsed
                break

        if data is None:
            return

        # Description
        desc = data.get("description")
        if desc and isinstance(desc, str):
            vaga.description = desc.strip()

        # Company
        org = data.get("hiringOrganization")
        if isinstance(org, dict):
            name = org.get("name", "").strip()
            if name:
                vaga.company = name

        # Location
        loc = data.get("jobLocation")
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            city = addr.get("addressLocality", "").strip()
            state = addr.get("addressRegion", "").strip()
            if city and state:
                vaga.location = f"{city}, {state}"
            elif city:
                vaga.location = city

        # Employment type
        emp_type = data.get("employmentType")
        if emp_type and isinstance(emp_type, str):
            vaga.job_type = emp_type.strip()

        # Publication date
        date_str = data.get("datePosted")
        if date_str:
            vaga.published_at = _parse_iso_date(date_str)


def _parse_iso_date(s: str) -> datetime | None:
    """Parse ISO date like '2026-01-30T08:00:00.0000000'."""
    s = s.strip()[:19]
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
