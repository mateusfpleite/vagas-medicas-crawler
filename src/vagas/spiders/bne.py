import asyncio
import json
import logging
import random
import re
from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from vagas.base_spider import BaseSpider
from vagas.browser import stealth_context
from vagas.models import Vaga
from vagas.scoring import medical_score, TITLE_THRESHOLD

log = logging.getLogger(__name__)

BASE_URL = "https://www.bne.com.br"
SEARCH_PAGES = [
    f"{BASE_URL}/vagas-de-emprego-para-medico",
    f"{BASE_URL}/vagas-de-emprego-para-medico-plantonista",
    f"{BASE_URL}/vagas-de-emprego-para-medico-do-trabalho",
    f"{BASE_URL}/vagas-de-emprego-para-medico-clinico-geral",
]
# Keep SEARCH_PAGE for backward compat (used as fallback URL in parse)
SEARCH_PAGE = SEARCH_PAGES[0]
API_PATH = "/vagas-de-emprego/api/v1/Lists/SequenceJobs"
FILTER_KEY_RE = re.compile(
    r"filterKey[^a-z0-9]*([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)

MAX_PAGES = 10  # safety cap

# City-specific searches — same coverage as Indeed spider
_CITY_SEARCHES = [
    # Capitals
    ("sao-paulo-sp", "São Paulo/SP"),
    ("rio-de-janeiro-rj", "Rio de Janeiro/RJ"),
    ("belo-horizonte-mg", "Belo Horizonte/MG"),
    ("curitiba-pr", "Curitiba/PR"),
    ("porto-alegre-rs", "Porto Alegre/RS"),
    ("salvador-ba", "Salvador/BA"),
    ("brasilia-df", "Brasília/DF"),
    ("fortaleza-ce", "Fortaleza/CE"),
    ("recife-pe", "Recife/PE"),
    ("goiania-go", "Goiânia/GO"),
    ("manaus-am", "Manaus/AM"),
    ("belem-pa", "Belém/PA"),
    ("florianopolis-sc", "Florianópolis/SC"),
    ("vitoria-es", "Vitória/ES"),
    # Interior
    ("campinas-sp", "Campinas/SP"),
    ("ribeirao-preto-sp", "Ribeirão Preto/SP"),
    ("sao-jose-dos-campos-sp", "São José dos Campos/SP"),
    ("sorocaba-sp", "Sorocaba/SP"),
    ("uberlandia-mg", "Uberlândia/MG"),
    ("ipatinga-mg", "Ipatinga/MG"),
    ("juiz-de-fora-mg", "Juiz de Fora/MG"),
    ("londrina-pr", "Londrina/PR"),
    ("joinville-sc", "Joinville/SC"),
    ("feira-de-santana-ba", "Feira de Santana/BA"),
]

MAX_AGE_DAYS = 60

# BNE IDs are roughly sequential across all job categories.
# Empirical rate: ~1500 IDs/day.  3x margin avoids false positives.
_BNE_IDS_PER_DAY = 1500
_ID_MARGIN = 3

# UI markers that appear after the real description content on detail pages
_DESC_CUT_MARKERS = ("Candidatar-me", "Compartilhe", "Copiado")

# JS templates to call BNE from within the browser (keeps GoCache cookies)
_FETCH_API_JS = """async (url) => {
    try {
        const r = await fetch(url);
        if (!r.ok) return { error: r.status };
        return await r.json();
    } catch (e) {
        return { error: e.message || 'fetch failed' };
    }
}"""

_FETCH_HTML_JS = """async (url) => {
    try {
        const r = await fetch(url);
        if (!r.ok) return { error: r.status };
        return await r.text();
    } catch (e) {
        return { error: e.message || 'fetch failed' };
    }
}"""


class BNESpider(BaseSpider):
    """
    Spider para o BNE (Banco Nacional de Empregos).

    Fluxo:
    1. Abre a página de busca via Playwright para obter o FilterKey.
    2. Chama a API REST via fetch() dentro do browser (mantém cookies Cloudflare).
    3. Pagina até esgotar resultados ou atingir MAX_PAGES.
    """

    name = "bne"

    # --- parsing ---------------------------------------------------------

    def parse(self, raw_data: dict) -> list[Vaga]:
        """Converte a resposta JSON da API em uma lista de Vaga."""
        items = raw_data.get("data", {}).get("listVagas", [])
        if items:
            log.debug("[%s] API item keys: %s", self.name, sorted(items[0].keys()))
        vagas: list[Vaga] = []
        for item in items:
            title = (item.get("Title") or "").strip()
            city = (item.get("City") or "").strip()
            state = (item.get("State") or "").strip()
            location = f"{city}/{state}" if city and state else city or state or "Brasil"
            url_path = item.get("UrlJob") or ""
            url = f"{BASE_URL}{url_path}" if url_path else SEARCH_PAGE
            external_id = str(item["Idf_Vaga"]) if item.get("Idf_Vaga") else None
            area = (item.get("Area") or "").strip() or None

            # Publication date
            published_at = self._parse_date(item)

            if not title:
                continue
            if medical_score(title) < TITLE_THRESHOLD:
                continue

            vagas.append(
                Vaga(
                    title=title,
                    location=location,
                    source="bne",
                    url=url,
                    external_id=external_id,
                    specialty=area,
                    published_at=published_at,
                )
            )
        return vagas

    @staticmethod
    def _parse_date(item: dict) -> datetime | None:
        """Try common BNE date field names."""
        for key in ("DateInsert", "DatePosted", "Date", "PublishDate", "Created"):
            val = item.get(key)
            if not val:
                continue
            if isinstance(val, (int, float)):
                try:
                    return datetime.fromtimestamp(val / 1000, tz=UTC)
                except (ValueError, OSError):
                    continue
            if isinstance(val, str):
                # Try ISO format: "2026-01-28T..." or "/Date(1234567890000)/"
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(val[:len(fmt) + 3], fmt).replace(tzinfo=UTC)
                    except ValueError:
                        continue
                # .NET JSON date: "/Date(1706400000000)/"
                m = re.search(r"/Date\((\d+)\)/", val)
                if m:
                    try:
                        return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=UTC)
                    except (ValueError, OSError):
                        pass
        return None

    @staticmethod
    def _extract_jsonld(html: str) -> dict | None:
        """Extract schema.org/JobPosting JSON-LD from HTML, or None."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all("script", type="application/ld+json"):
            if not tag.string:
                continue
            try:
                data = json.loads(tag.string)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                return data
        return None

    @staticmethod
    def parse_detail(html: str, vaga: Vaga) -> None:
        """Enrich a Vaga in-place from the BNE detail page.

        Strategy:
        1. JSON-LD (schema.org/JobPosting) for company and published_at.
        2. HTML <main> text for description, salary, job_type — cutting
           at UI markers to avoid junk.
        """
        vaga.raw_html = html

        # --- Phase 1: JSON-LD -------------------------------------------
        jsonld = BNESpider._extract_jsonld(html)
        if jsonld:
            org = jsonld.get("hiringOrganization", {}).get("name", "")
            if org and org.lower() not in ("confidencial",):
                vaga.company = org

            date_str = jsonld.get("datePosted")
            if date_str:
                try:
                    vaga.published_at = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    pass

        # --- Phase 2: HTML parsing --------------------------------------
        soup = BeautifulSoup(html, "lxml")
        main = soup.select_one("main")
        if not main:
            log.debug("[bne] no <main> tag for %s", vaga.url)
            return

        text = main.get_text(separator="\n")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for i, line in enumerate(lines):
            low = line.lower()
            next_val = lines[i + 1] if i + 1 < len(lines) else ""

            # Company from HTML (fallback if JSON-LD didn't set it)
            if not vaga.company and low.startswith("empresa:"):
                val = line.split(":", 1)[1].strip() or next_val
                if val and val.lower() not in ("confidencial", "a combinar"):
                    vaga.company = val

            elif low.startswith("salário:") or low.startswith("salario:"):
                val = line.split(":", 1)[1].strip() or next_val
                if val and val.lower() != "a combinar":
                    vaga.salary = val

            elif low.startswith("modalidade:"):
                val = line.split(":", 1)[1].strip() or next_val
                if val:
                    vaga.job_type = f"{vaga.job_type}, {val}" if vaga.job_type else val

            elif low.startswith("contrato:"):
                val = line.split(":", 1)[1].strip() or next_val
                if val:
                    vaga.job_type = f"{vaga.job_type}, {val}" if vaga.job_type else val

        # Description: everything after "Descrição Geral", cut at UI markers
        desc_marker = re.search(r"descri[çc][ãa]o\s+geral", text, re.IGNORECASE)
        if desc_marker:
            desc_text = text[desc_marker.end():].strip()
            # Cut at the first UI marker
            for marker in _DESC_CUT_MARKERS:
                pos = desc_text.find(marker)
                if pos >= 0:
                    desc_text = desc_text[:pos]
                    break
            desc_text = re.sub(r"\n{3,}", "\n\n", desc_text).strip()
            if desc_text and desc_text.lower() != "sine":
                vaga.description = desc_text

    # --- crawling --------------------------------------------------------

    async def _crawl_search(self, page, search_url: str, seen_ids: set[str], min_eid: int = 0) -> list[Vaga]:
        """Crawl a single search URL: get FilterKey, paginate API, return vagas."""
        try:
            await page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
        except Exception:
            log.warning("[%s] blocked or failed for %s", self.name, search_url)
            self._record_failure()
            return []

        html = await page.content()
        match = FILTER_KEY_RE.search(html)
        if not match:
            log.warning("[%s] Could not find FilterKey for %s", self.name, search_url)
            self._record_failure()
            return []

        filter_key = match.group(1)
        self._record_success()
        log.info("[%s] FilterKey for %s: %s", self.name, search_url.split("/")[-1], filter_key)

        vagas: list[Vaga] = []
        for page_num in range(MAX_PAGES):
            next_page = "true" if page_num > 0 else "false"
            api_url = (
                f"{BASE_URL}{API_PATH}"
                f"?FilterKey=filterKey:{filter_key}"
                f"&NextPage={next_page}&PrevPage=false"
            )
            log.info("[%s] %s API page %d", self.name, search_url.split("/")[-1], page_num + 1)

            data = await page.evaluate(_FETCH_API_JS, api_url)
            if not data or "error" in data:
                log.warning("[%s] API failed page %d: %s", self.name, page_num + 1, data)
                self._record_failure()
                break

            self._record_success()
            page_vagas = self.parse(data)
            if not page_vagas:
                log.info("[%s] no more results at page %d", self.name, page_num + 1)
                break

            # Deduplicate and filter old listings by ID
            new = 0
            skipped_old = 0
            for v in page_vagas:
                eid = v.external_id or ""
                if not eid:
                    continue
                if min_eid and eid.isdigit() and int(eid) < min_eid:
                    skipped_old += 1
                    continue
                if eid not in seen_ids:
                    seen_ids.add(eid)
                    vagas.append(v)
                    new += 1

            if skipped_old:
                log.debug("[%s] skipped %d old listings (id < %d)", self.name, skipped_old, min_eid)
            if new == 0:
                break

            new_match = FILTER_KEY_RE.search(str(data))
            if new_match:
                filter_key = new_match.group(1)

            await asyncio.sleep(1)

        return vagas

    async def crawl(self, known_ids: set[str] | None = None, locations: list[str] | None = None) -> list[Vaga]:
        seen_ids: set[str] = set()
        all_vagas: list[Vaga] = []

        ctx_manager = stealth_context(proxy=self._proxy)
        ctx = await ctx_manager.__aenter__()
        page = await ctx.new_page()
        browser_has_proxy = self._proxy is not None

        async def _restart_browser(block_resources: bool = False):
            nonlocal ctx_manager, ctx, page, browser_has_proxy
            log.info("[%s] restarting browser (proxy=%s, block_resources=%s)",
                     self.name, bool(self._proxy), block_resources)
            await ctx_manager.__aexit__(None, None, None)
            ctx_manager = stealth_context(
                proxy=self._proxy, block_resources=block_resources,
            )
            ctx = await ctx_manager.__aenter__()
            page = await ctx.new_page()
            browser_has_proxy = self._proxy is not None
            # Re-acquire Cloudflare/GoCache cookies by visiting a BNE page
            try:
                await page.goto(SEARCH_PAGES[0], wait_until="domcontentloaded")
                await asyncio.sleep(3)
            except Exception:
                log.warning("[%s] failed to re-acquire cookies after restart", self.name)

        async def _fetch_details(detail_vagas: list) -> tuple[int, list]:
            """Fetch detail pages. Returns (success_count, failed_vagas).

            Uses nonlocal `page` from crawl() so browser restarts take effect.
            """
            fetched = 0
            failed: list = []
            consecutive_errors = 0
            ip_rotations = 0
            max_rotations = 5

            for vaga in detail_vagas:
                try:
                    resp = await page.goto(vaga.url, wait_until="domcontentloaded")
                    if resp and resp.status >= 400:
                        raise Exception(f"HTTP {resp.status}")
                    await asyncio.sleep(1)
                    detail_html = await page.content()
                except Exception as e:
                    log.debug("[%s] detail failed %s: %s", self.name, vaga.url, e)
                    failed.append(vaga)
                    consecutive_errors += 1
                    if self._record_failure():
                        await _restart_browser(block_resources=True)
                        consecutive_errors = 0
                    elif self._proxy_active and consecutive_errors >= 3:
                        ip_rotations += 1
                        if ip_rotations > max_rotations:
                            log.warning("[%s] %d IP rotations reached, deferring remaining to retry",
                                        self.name, max_rotations)
                            failed.extend(detail_vagas[detail_vagas.index(vaga) + 1:])
                            break
                        log.info("[%s] rotating IP (%d/%d)",
                                 self.name, ip_rotations, max_rotations)
                        await _restart_browser(block_resources=True)
                        consecutive_errors = 0
                    elif consecutive_errors >= 10:
                        log.warning("[%s] %d consecutive failures (no proxy), deferring to retry",
                                    self.name, consecutive_errors)
                        failed.extend(detail_vagas[detail_vagas.index(vaga) + 1:])
                        break
                    continue

                consecutive_errors = 0
                ip_rotations = 0
                self._record_success()
                self.parse_detail(detail_html, vaga)
                fetched += 1
                log.debug("[%s] detail fetched: %s", self.name, vaga.url)
                await asyncio.sleep(3 + random.uniform(1, 2))

            return fetched, failed

        try:
            # Estimate minimum external_id to skip old listings.
            # Use max known ID as anchor; fall back to a conservative estimate.
            _anchor = max((int(x) for x in (known_ids or set()) if x.isdigit()), default=0)
            min_eid = _anchor - MAX_AGE_DAYS * _BNE_IDS_PER_DAY * _ID_MARGIN if _anchor else 0
            if min_eid > 0:
                log.info("[%s] filtering listings with id < %d (~%d days old)",
                         self.name, min_eid, MAX_AGE_DAYS)

            # 1. Crawl each search URL
            for search_url in SEARCH_PAGES:
                vagas = await self._crawl_search(page, search_url, seen_ids, min_eid)
                # If proxy activated during _crawl_search, restart browser with proxy
                if self._proxy and not browser_has_proxy:
                    await _restart_browser()
                all_vagas.extend(vagas)
                log.info("[%s] %s: %d new vagas (total: %d)",
                         self.name, search_url.split("/")[-1], len(vagas), len(all_vagas))
                await asyncio.sleep(random.uniform(2, 4))

            # 2. City-specific "médico" queries
            city_searches = _CITY_SEARCHES
            if locations:
                # Match CLI format ("Belo Horizonte, MG") against label ("Belo Horizonte/MG")
                # by normalizing separators before comparison
                def _norm(s: str) -> str:
                    return s.lower().replace(",", "").replace("/", " ").strip()

                city_searches = [
                    (slug, label) for slug, label in _CITY_SEARCHES
                    if any(_norm(loc) in _norm(label) for loc in locations)
                ]

            total_cities = len(city_searches)
            for i, (slug, label) in enumerate(city_searches, 1):
                url = f"{BASE_URL}/vagas-de-emprego-para-medico-em-{slug}"
                vagas = await self._crawl_search(page, url, seen_ids, min_eid)
                if self._proxy and not browser_has_proxy:
                    await _restart_browser()
                all_vagas.extend(vagas)
                log.info("[%s] city %d/%d '%s': %d new vagas (total: %d)",
                         self.name, i, total_cities, label, len(vagas), len(all_vagas))
                await asyncio.sleep(random.uniform(3, 5))

            # 3. Fetch detail pages via fetch() inside browser
            _known = known_ids or set()
            need_detail = [v for v in all_vagas
                           if v.url and v.url != SEARCH_PAGE
                           and v.external_id not in _known]
            log.info("[%s] %d vagas need detail (%d already known)",
                     self.name, len(need_detail), len(all_vagas) - len(need_detail))

            fetched, pending = await _fetch_details(need_detail)

            # Retry failed vagas with fresh IPs (max 3 retry passes)
            max_retry_passes = 3
            for retry in range(max_retry_passes):
                if not pending:
                    break
                log.info("[%s] retrying %d failed details (pass %d/%d)",
                         self.name, len(pending), retry + 1, max_retry_passes)
                await _restart_browser(block_resources=True)
                newly_fetched, pending = await _fetch_details(pending)
                if newly_fetched == 0:
                    log.info("[%s] retry pass made no progress, stopping", self.name)
                    break
                fetched += newly_fetched

            log.info("[%s] details fetched: %d/%d", self.name, fetched, len(all_vagas))

            # 4. Drop vagas with published_at older than MAX_AGE_DAYS (safety net)
            cutoff = datetime.now(UTC) - timedelta(days=MAX_AGE_DAYS)
            before = len(all_vagas)
            all_vagas = [v for v in all_vagas if v.published_at is None or v.published_at >= cutoff]
            dropped = before - len(all_vagas)
            if dropped:
                log.info("[%s] dropped %d vagas older than %d days", self.name, dropped, MAX_AGE_DAYS)
        finally:
            await ctx_manager.__aexit__(None, None, None)

        log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
        return all_vagas
