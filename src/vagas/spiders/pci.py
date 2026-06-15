import asyncio
import json
import logging
import random
import re
from datetime import UTC, date, datetime

import httpx
from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.models import Vaga

log = logging.getLogger(__name__)

BASE_URL = "https://www.pciconcursos.com.br"

# Extract slug from noticias URL: /noticias/some-slug -> some-slug
_SLUG_RE = re.compile(r"/noticias/([a-z0-9][a-z0-9-]+[a-z0-9])$", re.IGNORECASE)

# Extract salary: "até R$ 5.286,42" — works with or without vacancy count prefix
_SALARY_RE = re.compile(r"até R\$\s*([\d.,]+)")

# Extract city + state from headline: "... de Machado - MG abre ..."
# Uses the last "de {city}" before "- UF" to handle compound org names.
_LOCATION_RE = re.compile(r"\bde\s+(.+?)\s*[-–]\s*([A-Z]{2})\b")

# Extract DD/MM/YYYY dates from div.ce deadline text
_DEADLINE_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")

# Detect medical positions in article body (handles plural: Médicos/Médicas)
_MEDICAL_RE = re.compile(r"\bm[ée]dic[oa]?s?\b", re.IGNORECASE)
# Exclude veterinary matches
_VETERINARY_RE = re.compile(r"\bveterin[aá]ri[oa]?s?\b", re.IGNORECASE)


class PCISpider(BaseSpider):
    """Spider para PCI Concursos (pciconcursos.com.br).

    Crawls public concursos/processos seletivos for medical positions.
    httpx-only (static HTML, no anti-bot).
    """

    name = "pci"

    _SEARCH_SLUGS = [
        "medico",
        "medico-clinico-geral",
        "medico-clinico",
        "medico-psf",
        "medico-esf",
        "medico-pediatra",
        "medico-psiquiatra",
        "medico-cardiologista",
        "medico-do-trabalho",
        "medico-ginecologista",
        "medico-ginecologista-obstetra",
        "medico-cirurgiao-geral",
        "medico-neurologista",
        "medico-oftalmologista",
        "medico-dermatologista",
        "medico-urologista",
        "medico-endocrinologista",
        "medico-ortopedista",
        "medico-plantonista",
        "medico-geriatra",
        "medico-gastroenterologista",
        "medico-nefrologista",
        "medico-reumatologista",
        "medico-especialista",
        "medico-generalista",
    ]

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    async def crawl(
        self,
        known_ids: set[str] | None = None,
        locations: list[str] | None = None,
    ) -> list[Vaga]:
        seen_slugs: set[str] = set()
        all_vagas: list[Vaga] = []

        async with httpx.AsyncClient(
            headers=self._HEADERS,
            follow_redirects=True,
            timeout=15.0,
            proxy=self._proxy,
        ) as client:
            # Phase 1: listing pages
            for slug in self._SEARCH_SLUGS:
                url = f"{BASE_URL}/vagas/{slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        self._record_failure()
                        log.warning("[%s] listing %s -> %d", self.name, slug, resp.status_code)
                        continue
                    self._record_success()
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] listing %s failed: %s", self.name, slug, e)
                    continue

                vagas = self.parse_listing(resp.text)
                new = 0
                for v in vagas:
                    if v.external_id and v.external_id not in seen_slugs:
                        seen_slugs.add(v.external_id)
                        all_vagas.append(v)
                        new += 1

                log.info("[%s] slug '%s': %d results (%d new)", self.name, slug, len(vagas), new)
                await asyncio.sleep(1 + random.uniform(0.5, 1.5))

            log.info("[%s] total unique from listings: %d", self.name, len(all_vagas))

            # Phase 2: detail pages (skip known_ids)
            _known = known_ids or set()
            need_detail = [v for v in all_vagas if v.external_id not in _known]
            log.info(
                "[%s] %d vagas need detail (%d already known)",
                self.name, len(need_detail), len(all_vagas) - len(need_detail),
            )

            fetched = 0
            discarded = 0
            for vaga in need_detail:
                try:
                    resp = await client.get(vaga.url)
                    if resp.status_code == 200:
                        if self.parse_detail(resp.text, vaga):
                            fetched += 1
                            self._record_success()
                        else:
                            discarded += 1
                    else:
                        self._record_failure()
                        log.warning("[%s] detail %s -> %d", self.name, vaga.url, resp.status_code)
                except Exception as e:
                    self._record_failure()
                    log.warning("[%s] detail failed %s: %s", self.name, vaga.url, e)

                await asyncio.sleep(1.5 + random.uniform(0.5, 1.5))

        # Remove vagas where detail had no medical positions.
        # parse_detail only sets description when returning True,
        # so description=None means non-medical or unfetched.
        # Known vagas (already in DB) are kept as-is.
        all_vagas = [
            v for v in all_vagas
            if v.external_id in _known or v.description is not None
        ]

        log.info("[%s] details: %d fetched, %d discarded (non-medical)", self.name, fetched, discarded)
        log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
        return all_vagas

    def parse_listing(self, html: str, today: date | None = None) -> list[Vaga]:
        """Extract concurso cards from a listing page.

        Skips cards whose inscription deadline has already passed.
        ``today`` can be injected for testing; defaults to date.today().
        """
        _today = today or date.today()
        soup = BeautifulSoup(html, "lxml")
        vagas: list[Vaga] = []
        seen: set[str] = set()
        skipped_expired = 0

        # da = highlighted, na = normal/recent, ea = older entries
        for card in soup.select("div.da, div.na, div.ea"):
            # --- Freshness filter: skip cards with past deadlines ---
            ce = card.select_one("div.ce")
            if ce:
                deadline = _parse_deadline(ce.get_text(separator=" ", strip=True))
                if deadline and deadline < _today:
                    skipped_expired += 1
                    continue

            link = card.select_one("div.ca a")
            if not link:
                continue

            href = link.get("href", "")
            m = _SLUG_RE.search(href)
            if not m:
                continue

            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)

            company = link.get_text(strip=True)
            title = link.get("title", company)

            state_el = card.select_one("div.cc")
            state = state_el.get_text(strip=True) if state_el else None

            salary = None
            salary_max = None
            cd_el = card.select_one("div.cd")
            if cd_el:
                cd_text = cd_el.get_text(separator=" ", strip=True)
                m_sal = _SALARY_RE.search(cd_text)
                if m_sal:
                    raw = m_sal.group(1)
                    salary = f"até R$ {raw}"
                    try:
                        salary_max = float(raw.replace(".", "").replace(",", "."))
                    except ValueError:
                        pass

            url = href if href.startswith("http") else f"{BASE_URL}{href}"

            vagas.append(Vaga(
                title=title,
                location=state or "Brasil",
                source=self.name,
                url=url,
                company=company,
                salary=salary,
                salary_max=salary_max,
                salary_period="MONTHLY",
                external_id=slug,
            ))

        if skipped_expired:
            log.info("[%s] skipped %d cards with expired deadlines", "pci", skipped_expired)

        return vagas

    @staticmethod
    def parse_detail(html: str, vaga: Vaga) -> bool:
        """Enrich a Vaga in-place from a PCI detail page.

        Returns True if human-doctor positions were found, False otherwise.
        IMPORTANT: Only sets vaga.description when returning True — the
        crawl method's post-filter relies on description being None for
        non-medical vagas.
        """
        vaga.raw_html = html
        soup = BeautifulSoup(html, "lxml")

        # --- JSON-LD: datePublished ---
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            if not ld_tag.string:
                continue
            try:
                data = json.loads(ld_tag.string)
            except json.JSONDecodeError:
                continue

            articles = []
            if isinstance(data, dict) and "@graph" in data:
                articles = [
                    n for n in data["@graph"]
                    if isinstance(n, dict) and n.get("@type") == "NewsArticle"
                ]
            elif isinstance(data, dict) and data.get("@type") == "NewsArticle":
                articles = [data]

            if articles:
                date_str = articles[0].get("datePublished")
                if date_str:
                    vaga.published_at = _parse_iso_date(date_str)
                break

        # --- Headline -> city, state ---
        h1 = soup.select_one("h1[itemprop='headline']")
        if h1:
            loc_m = _LOCATION_RE.search(h1.get_text(strip=True))
            if loc_m:
                vaga.location = f"{loc_m.group(1).strip()}, {loc_m.group(2).strip()}"

        # --- Fallback date from abbr.published ---
        if not vaga.published_at:
            abbr = soup.select_one("abbr.published[title]")
            if abbr:
                vaga.published_at = _parse_iso_date(abbr.get("title", ""))

        # --- Article body: detect medical positions ---
        body = soup.select_one("div[itemprop='articleBody']")
        if not body:
            return False

        has_medical = False
        for el in body.select("li, p"):
            text = el.get_text(strip=True)
            if _MEDICAL_RE.search(text) and not _VETERINARY_RE.search(text):
                has_medical = True
                break

        if not has_medical:
            return False

        # Only set description for medical vagas (filter depends on this)
        vaga.description = body.get_text(separator="\n", strip=True) or None
        return True


def _parse_deadline(text: str) -> date | None:
    """Extract inscription deadline from div.ce text.

    Handles: "05/03/2026", "Reaberto até 12/02/2026", "23/03 a 22/04/2026".
    Returns the last DD/MM/YYYY date found (the deadline).
    """
    matches = _DEADLINE_DATE_RE.findall(text)
    if not matches:
        return None
    try:
        return datetime.strptime(matches[-1], "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_iso_date(s: str) -> datetime | None:
    """Parse ISO date like '2026-01-12T19:12:56-03:00'."""
    s = s.strip()
    # Remove colon in timezone offset: -03:00 -> -0300
    s = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", s)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None
