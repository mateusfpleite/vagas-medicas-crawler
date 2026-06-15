import asyncio
import logging
import random
import re
import unicodedata
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_context
from vagas.models import Vaga
from vagas.scoring import medical_score, TITLE_THRESHOLD

log = logging.getLogger(__name__)

# JS snippet to extract job data from Indeed's mosaic provider
_MOSAIC_EXTRACT_JS = """() => {
    try {
        const pd = window.mosaic.providerData;
        const jc = pd['mosaic-provider-jobcards'];
        const model = jc.metaData.mosaicProviderJobCardsModel;
        return model.results.map(r => ({
            displayTitle: r.displayTitle || r.title || '',
            company: r.company || '',
            formattedLocation: r.formattedLocation || '',
            jobLocationCity: r.jobLocationCity || '',
            jobLocationState: r.jobLocationState || '',
            jobkey: r.jobkey || '',
            normTitle: r.normTitle || '',
            jobTypes: r.jobTypes || [],
            salarySnippet: r.salarySnippet || null,
            extractedSalary: r.extractedSalary || null,
            snippet: r.snippet || '',
            taxonomyAttributes: r.taxonomyAttributes || [],
            pubDate: r.pubDate || null,
        }));
    } catch (e) {
        return null;
    }
}"""

# Pattern: "Médico <specialty> - <suffix>" or "Médico <specialty>"
_SPECIALTY_RE = re.compile(
    r"^M[ée]dico(?:\(a\))?\s+(.+?)(?:\s*[-–|].+)?$",
    re.IGNORECASE,
)

# Title keywords that indicate a non-doctor role even if normTitle matches
_TITLE_EXCLUDE_RE = re.compile(
    r"\b(veterin[áa]ri[oa]|enfermeiro|auxiliar|t[ée]cnico\b.*enfermagem|conteudista)\b",
    re.IGNORECASE,
)

# normTitle prefix for medical jobs (case-insensitive)
_MEDICAL_NORM_PREFIX = "medico"
# Standalone specialty normTitles that are also medical doctors
_MEDICAL_NORM_EXACT = {
    "endocrinologista", "oftalmologista", "ortopedista", "pneumologista",
    "urologista", "generalista", "geriatra", "hematologista",
    "infectologista", "nefrologista", "reumatologista",
}

# Queries to search — specialty-specific queries surface different results
# Regional locations — broad "médico" query per city surfaces local results
# that the nationwide search misses
_LOCATION_FILTERS = [
    # Capitals
    "São Paulo, SP",
    "Rio de Janeiro, RJ",
    "Belo Horizonte, MG",
    "Curitiba, PR",
    "Porto Alegre, RS",
    "Salvador, BA",
    "Brasília, DF",
    "Fortaleza, CE",
    "Recife, PE",
    "Goiânia, GO",
    "Manaus, AM",
    "Belém, PA",
    "Florianópolis, SC",
    "Vitória, ES",
    # Interior metro hubs
    "Campinas, SP",
    "Ribeirão Preto, SP",
    "São José dos Campos, SP",
    "Sorocaba, SP",
    "Uberlândia, MG",
    "Ipatinga, MG",
    "Juiz de Fora, MG",
    "Londrina, PR",
    "Joinville, SC",
    "Feira de Santana, BA",
]

_SEARCH_QUERIES = [
    "médico",
    "médico clínico geral",
    "médico plantonista",
    "médico do trabalho",
    "médico pediatra",
    "médico ginecologista",
    "médico cardiologista",
    "médico ortopedista",
    "médico neurologista",
    "médico psiquiatra",
    "médico cirurgião",
    "médico intensivista",
    "médico dermatologista",
    "médico anestesista",
    "médico oftalmologista",
    "médico endocrinologista",
    "médico generalista",
    "médico pneumologista",
    "médico infectologista",
    "médico geriatra",
]


def _strip_accents(s: str) -> str:
    """Remove diacritics: 'Médico' -> 'Medico'."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _is_medical_norm(norm_title: str) -> bool:
    """Check if a normTitle represents a medical doctor job."""
    norm = _strip_accents(norm_title.strip().lower())
    # "Medico", "Médico Cardiologista", "Médico Clínico Geral", etc.
    if norm.startswith(_MEDICAL_NORM_PREFIX):
        return True
    # Standalone specialties: "Oftalmologista", "Generalista", etc.
    return norm in _MEDICAL_NORM_EXACT


class _CloudflareBlocked(Exception):
    """Raised when Cloudflare challenge is detected, signaling browser restart."""
    def __init__(self, query: str, location: str):
        self.query = query
        self.location = location
        super().__init__(f"Cloudflare blocked query='{query}' location='{location}'")


class IndeedSpider(BaseSpider):
    """
    Spider para o Indeed Brasil (br.indeed.com).

    Extrai dados estruturados de window.mosaic.providerData.
    Usa múltiplas queries de busca com browser fresco por query
    para contornar Cloudflare e maximizar cobertura.
    """

    name = "indeed"
    WAIT_SELECTOR = ".job_seen_beacon"
    BASE_URL = "https://br.indeed.com"

    def parse_mosaic(self, results: list[dict]) -> list[Vaga]:
        """Converte resultados do mosaic JS em lista de Vaga filtrada."""
        vagas: list[Vaga] = []

        for r in results:
            # Filter: only accept medical jobs
            norm = r.get("normTitle", "")
            if not _is_medical_norm(norm):
                continue

            title = r.get("displayTitle", "").strip()
            if not title:
                continue

            # Exclude non-doctor roles that slip through normTitle filter
            if _TITLE_EXCLUDE_RE.search(title):
                continue

            # Defense-in-depth: scoring filter for edge cases
            if medical_score(title) < TITLE_THRESHOLD:
                continue

            jobkey = r.get("jobkey", "")

            # Salary
            salary_text = None
            salary_min = None
            salary_max = None
            salary_period = None

            snippet_obj = r.get("salarySnippet") or {}
            if snippet_obj.get("text"):
                salary_text = snippet_obj["text"]

            extracted = r.get("extractedSalary")
            if extracted:
                raw_min = extracted.get("min")
                raw_max = extracted.get("max")
                if raw_min is not None and raw_min > 0:
                    salary_min = float(raw_min)
                if raw_max is not None and raw_max > 0:
                    salary_max = float(raw_max)
                salary_period = extracted.get("type")

            # Job type
            job_types = r.get("jobTypes") or []
            job_type = ", ".join(job_types) if job_types else None

            # Benefits from taxonomyAttributes
            benefits = None
            for attr in r.get("taxonomyAttributes") or []:
                if attr.get("label") == "benefits":
                    items = [a["label"] for a in attr.get("attributes", []) if "label" in a]
                    if items:
                        benefits = items
                    break

            # Description from snippet (strip HTML)
            snippet_html = r.get("snippet", "")
            description = None
            if snippet_html:
                soup = BeautifulSoup(snippet_html, "lxml")
                text = soup.get_text(separator=" ", strip=True)
                if text:
                    description = text

            # Specialty from title
            specialty = self._extract_specialty(title)

            # Publication date (epoch ms)
            published_at = None
            pub_date_raw = r.get("pubDate")
            if pub_date_raw and isinstance(pub_date_raw, (int, float)):
                try:
                    published_at = datetime.fromtimestamp(pub_date_raw / 1000, tz=UTC)
                except (ValueError, OSError):
                    pass

            vagas.append(
                Vaga(
                    title=title,
                    location=r.get("formattedLocation", "Brasil"),
                    source=self.name,
                    url=f"{self.BASE_URL}/viewjob?jk={jobkey}" if jobkey else "",
                    company=r.get("company") or None,
                    salary=salary_text,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_period=salary_period,
                    job_type=job_type,
                    specialty=specialty,
                    external_id=jobkey or None,
                    description=description,
                    benefits=benefits,
                    published_at=published_at,
                )
            )

        log.info("Indeed parse_mosaic: %d vagas (from %d results)", len(vagas), len(results))
        return vagas

    @staticmethod
    def _extract_specialty(title: str) -> str | None:
        """Extrai especialidade do título. Ex: 'Médico Cardiologista' -> 'Cardiologista'."""
        m = _SPECIALTY_RE.match(title.strip())
        if not m:
            return None
        specialty = m.group(1).strip()
        # Skip generic suffixes that aren't specialties
        if not specialty or specialty.lower() in ("", "offshore"):
            return None
        return specialty

    _MAX_RETRIES = 2
    _CF_CHALLENGE_TITLES = {"just a moment...", "attention required"}

    async def _is_cloudflare_challenge(self, page) -> bool:
        """Detect Cloudflare challenge pages early without waiting for timeout."""
        title = (await page.title()).strip().lower()
        return title in self._CF_CHALLENGE_TITLES

    async def _fetch_query(self, context, query: str, location: str = "Brasil") -> list[dict]:
        """Fetch mosaic results for a single query+location.

        Uses a fresh page from the given browser context per attempt.
        Retries up to _MAX_RETRIES times with exponential backoff.
        Raises _CloudflareBlocked if Cloudflare challenge is detected.
        """
        from urllib.parse import quote_plus

        url = f"{self.BASE_URL}/jobs?q={quote_plus(query)}&l={quote_plus(location)}"

        for attempt in range(1 + self._MAX_RETRIES):
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")

                # Early Cloudflare detection — don't waste 20s on a challenge page
                await asyncio.sleep(1)
                if await self._is_cloudflare_challenge(page):
                    log.warning("[%s] Cloudflare challenge detected for '%s' location='%s'",
                                self.name, query, location)
                    raise _CloudflareBlocked(query, location)

                # Wait for job cards OR a legitimate no-results page.
                found = await page.wait_for_selector(
                    f"{self.WAIT_SELECTOR}, .jobsearch-NoResult-messageContainer",
                    timeout=20000,
                )
                await asyncio.sleep(random.uniform(1, 3))

                # No-results page — don't retry, just move on
                if found and await found.evaluate(
                    "el => el.matches('.jobsearch-NoResult-messageContainer')"
                ):
                    log.info("[%s] no results for query '%s' location='%s'",
                             self.name, query, location)
                    return []

                results = await page.evaluate(_MOSAIC_EXTRACT_JS)
                if results:
                    log.info("[%s] query '%s' location='%s': %d results",
                             self.name, query, location, len(results))
                    return results

                log.warning("[%s] no mosaic data for query '%s' location='%s'",
                            self.name, query, location)
                return []
            except _CloudflareBlocked:
                raise
            except Exception as exc:
                if attempt < self._MAX_RETRIES:
                    delay = random.uniform(5, 10) * (attempt + 1)
                    log.info("[%s] attempt %d failed for '%s' location='%s': %s — retrying in %.0fs",
                             self.name, attempt + 1, query, location, exc, delay)
                    await asyncio.sleep(delay)
                else:
                    log.warning("[%s] failed after %d attempts for '%s' location='%s': %s",
                                self.name, 1 + self._MAX_RETRIES, query, location, exc)
            finally:
                await page.close()

        return []

    async def _run_query_with_fresh_browser(self, query: str, location: str) -> list[dict]:
        """Run a single query using a fresh browser to avoid Cloudflare fingerprinting."""
        async with stealth_context(proxy=self._proxy) as context:
            return await self._fetch_query(context, query, location)

    async def crawl(self, known_ids=None, locations=None) -> list[Vaga]:
        seen_keys: set[str] = set()
        all_results: list[dict] = []

        def _collect(results):
            new = 0
            for r in results:
                jk = r.get("jobkey", "")
                if jk and jk not in seen_keys:
                    seen_keys.add(jk)
                    all_results.append(r)
                    new += 1
            return new

        target_locations = locations or ["Brasil"]

        # 1. Specialty queries — fresh browser per query to avoid CF fingerprinting
        for loc in target_locations:
            for query in _SEARCH_QUERIES:
                try:
                    results = await self._run_query_with_fresh_browser(query, loc)
                except _CloudflareBlocked:
                    self._record_failure()
                    results = []

                _collect(results)

                if results:
                    self._record_success()
                else:
                    self._record_failure()

                await asyncio.sleep(random.uniform(6, 12))

            log.info("[%s] after specialty queries for '%s': %d unique results",
                     self.name, loc, len(all_results))

        # 2. Broad "médico" query per city (skip when explicit locations provided)
        if not locations:
            for location in _LOCATION_FILTERS:
                try:
                    results = await self._run_query_with_fresh_browser("médico", location)
                except _CloudflareBlocked:
                    self._record_failure()
                    results = []

                new = _collect(results)
                if new:
                    log.info("[%s] location '%s': %d new results", self.name, location, new)

                if results:
                    self._record_success()
                else:
                    self._record_failure()

                await asyncio.sleep(random.uniform(6, 12))

        log.info("[%s] total unique results: %d", self.name, len(all_results))
        return self.parse_mosaic(all_results)
