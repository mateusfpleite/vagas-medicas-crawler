import asyncio
import logging
import random
import re
from datetime import UTC, datetime

import httpx

from vagas.base_spider import BaseSpider
from vagas.filters import is_medical_title
from vagas.models import Vaga

log = logging.getLogger(__name__)

API_URL = "https://portal.api.gupy.io/api/job"

_SEARCH_QUERIES = [
    "médico",
    "médico clínico geral",
    "médico plantonista",
    "médico do trabalho",
    "pediatra",
    "ginecologista",
    "cardiologista",
    "ortopedista",
    "psiquiatra",
    "cirurgião",
    "intensivista",
    "anestesista",
    "dermatologista",
    "neurologista",
    "oftalmologista",
    "endocrinologista",
]

# Gupy API returns full state names; map to UF abbreviations.
_STATE_TO_UF: dict[str, str] = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}

_WORKPLACE_MAP: dict[str, str] = {
    "on-site": "Presencial",
    "remote": "Remoto",
    "hybrid": "Híbrido",
}

# Strip accents for state name lookup
_ACCENT_RE = re.compile(r"[\u0300-\u036f]")


def _strip_accents(s: str) -> str:
    import unicodedata
    return _ACCENT_RE.sub("", unicodedata.normalize("NFD", s))


def _state_abbrev(state: str) -> str | None:
    """Convert full state name to UF abbreviation."""
    key = _strip_accents(state).lower().strip()
    return _STATE_TO_UF.get(key)


def _build_location(city: str | None, state: str | None) -> str:
    """Build location string from city and state."""
    uf = _state_abbrev(state) if state else None
    if city and uf:
        return f"{city}, {uf}"
    if city:
        return city
    if uf:
        return uf
    return "Brasil"


def _parse_published_date(date_str: str | None) -> datetime | None:
    """Parse ISO 8601 date from Gupy API (e.g. '2025-08-17T20:31:08.667Z')."""
    if not date_str:
        return None
    s = date_str.strip()
    # Replace trailing Z with +00:00 for fromisoformat
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # Fallback: try without fractional seconds
        s = s.split(".")[0]
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return None


class GupySpider(BaseSpider):
    """Spider para o portal Gupy (gupy.io).

    Uses the public REST API at portal.api.gupy.io.
    No Playwright needed — plain httpx JSON requests.
    """

    name = "gupy"

    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    async def crawl(
        self,
        known_ids: set[str] | None = None,
        locations: list[str] | None = None,
    ) -> list[Vaga]:
        seen_ids: set[str] = set()
        raw_results: list[dict] = []
        _known = known_ids or set()

        async with httpx.AsyncClient(
            headers=self._HEADERS,
            follow_redirects=True,
            timeout=15.0,
            proxy=self._proxy,
        ) as client:
            for query in _SEARCH_QUERIES:
                offset = 0

                while True:
                    params = {"name": query, "offset": offset}
                    try:
                        resp = await client.get(API_URL, params=params)
                        if resp.status_code != 200:
                            self._record_failure()
                            log.warning(
                                "[%s] query '%s' offset=%d -> %d",
                                self.name, query, offset, resp.status_code,
                            )
                            break
                        self._record_success()
                    except Exception as e:
                        self._record_failure()
                        log.warning("[%s] query '%s' failed: %s", self.name, query, e)
                        break

                    data = resp.json()
                    items = data.get("data", [])
                    pagination = data.get("pagination", {})
                    total = pagination.get("total", 0)
                    page_limit = pagination.get("limit", 10)

                    for item in items:
                        item_id = str(item.get("id", ""))
                        if not item_id or item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)
                        if item_id in _known:
                            continue
                        raw_results.append(item)

                    offset += page_limit
                    if offset >= total or not items:
                        break

                    await asyncio.sleep(random.uniform(0.5, 1.5))

                log.info(
                    "[%s] query '%s': %d seen, %d raw collected",
                    self.name, query, len(seen_ids), len(raw_results),
                )
                await asyncio.sleep(random.uniform(1.0, 2.0))

        vagas = self.parse_results(raw_results)
        log.info("[%s] crawl finished: %d vagas", self.name, len(vagas))
        return vagas

    @staticmethod
    def parse_results(data: list[dict]) -> list[Vaga]:
        """Convert raw API dicts to Vaga objects, filtering non-medical titles."""
        vagas: list[Vaga] = []
        skipped_pool = 0
        skipped_title = 0

        for item in data:
            # Skip talent pools — not active job openings, just CV collection
            if item.get("type") == "vacancy_type_talent_pool":
                skipped_pool += 1
                log.debug("[gupy] skip talent_pool: %s", item.get("name", "?"))
                continue

            title = item.get("name", "").strip()
            if not title:
                continue

            if not is_medical_title(title):
                skipped_title += 1
                log.debug("[gupy] skip non-medical: %s", title)
                continue

            location = _build_location(
                item.get("city"),
                item.get("state"),
            )

            workplace = item.get("workplaceType", "")
            job_type = _WORKPLACE_MAP.get(workplace)

            vagas.append(Vaga(
                title=title,
                location=location,
                source="gupy",
                url=item.get("jobUrl", ""),
                company=item.get("careerPageName"),
                external_id=str(item.get("id", "")),
                description=item.get("description"),
                raw_html=item.get("description"),
                published_at=_parse_published_date(item.get("publishedDate")),
                job_type=job_type,
            ))

        if skipped_pool or skipped_title:
            log.info(
                "[gupy] parse_results: %d kept, %d talent_pool, %d non-medical (of %d raw)",
                len(vagas), skipped_pool, skipped_title, len(data),
            )

        return vagas
