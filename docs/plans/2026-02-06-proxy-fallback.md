# Proxy Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add automatic proxy fallback to all spiders — starts without proxy, activates after 3 consecutive failures, stays active for the rest of that spider.

**Architecture:** `PROXY_URL` env var in `.env`. `BaseSpider` tracks consecutive failures and exposes `self._proxy` (URL or None). `_record_failure()` returns `True` when proxy just activated (signals browser restart). `browser.py` accepts optional `proxy` param passed to Playwright launch. Each spider calls `_record_failure()`/`_record_success()` at actual failure/success points (not inferred from empty results). httpx clients also receive `self._proxy`.

**Tech Stack:** Playwright proxy support (built-in), httpx proxy param (built-in), no new dependencies.

**Design decisions:**
- Proxy activates after 3 consecutive failures and stays active for the rest of that spider. Next spider starts fresh (new `__init__`).
- BNE uses browser `fetch()` to keep Cloudflare/GoCache cookies. After browser restart, we navigate to a BNE page to re-acquire cookies before continuing.
- VagasCom creates a fresh browser per search URL, so proxy activation naturally takes effect on the next URL. For the detail phase, the browser is created once with the current proxy state.
- InfoJobs listing phase creates a fresh browser per query (same as VagasCom). The httpx detail phase creates the client once with current proxy state.
- For both VagasCom and InfoJobs, if proxy activates mid-detail, the current session continues without proxy. This is an acceptable trade-off — detail phases are less likely to be blocked than listing phases.

---

### Task 1: BaseSpider proxy tracking

**Files:**
- Modify: `src/vagas/base_spider.py:1-20`
- Test: `tests/test_proxy.py` (create)

**Step 1: Write the failing tests**

```python
# tests/test_proxy.py
import os
from unittest.mock import patch

from vagas.base_spider import BaseSpider


class ConcreteSpider(BaseSpider):
    """Minimal concrete spider for testing."""
    name = "test"


def test_proxy_inactive_by_default():
    spider = ConcreteSpider()
    assert spider._proxy is None


def test_proxy_activates_after_3_failures():
    with patch.dict(os.environ, {"PROXY_URL": "http://user:pass@proxy:1234"}):
        spider = ConcreteSpider()
        spider._record_failure()
        spider._record_failure()
        assert spider._proxy is None
        spider._record_failure()
        assert spider._proxy == "http://user:pass@proxy:1234"


def test_proxy_stays_active_after_activation():
    with patch.dict(os.environ, {"PROXY_URL": "http://user:pass@proxy:1234"}):
        spider = ConcreteSpider()
        for _ in range(3):
            spider._record_failure()
        assert spider._proxy is not None
        spider._record_success()
        assert spider._proxy is not None  # does NOT deactivate


def test_proxy_never_activates_without_env_var():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PROXY_URL", None)
        spider = ConcreteSpider()
        for _ in range(10):
            spider._record_failure()
        assert spider._proxy is None


def test_record_success_resets_failure_count():
    with patch.dict(os.environ, {"PROXY_URL": "http://proxy:1234"}):
        spider = ConcreteSpider()
        spider._record_failure()
        spider._record_failure()
        spider._record_success()  # reset
        spider._record_failure()
        assert spider._proxy is None  # only 1 failure since reset


def test_proxy_threshold_is_3():
    assert BaseSpider.PROXY_THRESHOLD == 3


def test_record_failure_returns_true_on_activation():
    with patch.dict(os.environ, {"PROXY_URL": "http://proxy:1234"}):
        spider = ConcreteSpider()
        assert spider._record_failure() is False
        assert spider._record_failure() is False
        assert spider._record_failure() is True  # proxy just activated
        assert spider._record_failure() is False  # already active, no new activation


def test_record_failure_returns_false_without_proxy():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PROXY_URL", None)
        spider = ConcreteSpider()
        for _ in range(10):
            assert spider._record_failure() is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_proxy.py -v`
Expected: FAIL — `BaseSpider` has no `_proxy`, `_record_failure`, etc.

**Step 3: Implement BaseSpider proxy tracking**

Replace the entire `src/vagas/base_spider.py`:

```python
# src/vagas/base_spider.py
import logging
import os

from vagas.models import Vaga

log = logging.getLogger(__name__)


class BaseSpider:
    name: str = "base"

    PROXY_THRESHOLD = 3

    def __init__(self):
        self._consecutive_failures = 0
        self._proxy_active = False
        self._proxy_url: str | None = os.environ.get("PROXY_URL")

    def _record_failure(self) -> bool:
        """Record a failure. Returns True if proxy was just activated."""
        self._consecutive_failures += 1
        if (
            self._proxy_url
            and not self._proxy_active
            and self._consecutive_failures >= self.PROXY_THRESHOLD
        ):
            self._proxy_active = True
            log.warning(
                "[%s] %d consecutive failures — activating proxy",
                self.name,
                self._consecutive_failures,
            )
            self._consecutive_failures = 0
            return True
        return False

    def _record_success(self):
        self._consecutive_failures = 0

    @property
    def _proxy(self) -> str | None:
        return self._proxy_url if self._proxy_active else None

    def parse(self, raw_data) -> list[Vaga]:
        raise NotImplementedError

    async def crawl(
        self,
        known_ids: set[str] | None = None,
        locations: list[str] | None = None,
    ) -> list[Vaga]:
        raise NotImplementedError
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_proxy.py -v`
Expected: all 8 PASS

**Step 5: Commit**

```
feat: add proxy fallback tracking to BaseSpider
```

---

### Task 2: browser.py proxy parameter

**Files:**
- Modify: `src/vagas/browser.py:1-52`
- Test: `tests/test_browser_proxy.py` (create)

**Step 1: Write the failing test**

```python
# tests/test_browser_proxy.py
from unittest.mock import AsyncMock, patch

from vagas.browser import stealth_context


async def test_stealth_context_passes_proxy_to_launch():
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("vagas.browser.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_apw.return_value.__aexit__ = AsyncMock(return_value=False)

        async with stealth_context(proxy="http://user:pass@proxy:1234") as ctx:
            pass

        mock_chromium.launch.assert_called_once()
        call_kwargs = mock_chromium.launch.call_args[1]
        assert call_kwargs["proxy"] == {"server": "http://user:pass@proxy:1234"}


async def test_stealth_context_no_proxy_by_default():
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("vagas.browser.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_apw.return_value.__aexit__ = AsyncMock(return_value=False)

        async with stealth_context() as ctx:
            pass

        call_kwargs = mock_chromium.launch.call_args[1]
        assert "proxy" not in call_kwargs
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_browser_proxy.py -v`
Expected: FAIL — `stealth_context()` doesn't accept `proxy` param.

**Step 3: Add proxy parameter to browser.py**

Replace the entire `src/vagas/browser.py`:

```python
import logging
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

log = logging.getLogger(__name__)

_stealth = Stealth()


@asynccontextmanager
async def stealth_page(headless: bool = True, proxy: str | None = None):
    """Abre um browser Playwright com stealth e retorna uma Page."""
    async with stealth_context(headless=headless, proxy=proxy) as context:
        page = await context.new_page()
        yield page


@asynccontextmanager
async def stealth_context(headless: bool = True, proxy: str | None = None):
    """Abre um browser Playwright com stealth e retorna um BrowserContext."""
    async with async_playwright() as p:
        launch_opts: dict = {"headless": headless}
        if proxy:
            launch_opts["proxy"] = {"server": proxy}
        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        await _stealth.apply_stealth_async(context)
        try:
            yield context
        finally:
            await browser.close()


async def fetch_rendered_html(
    url: str, wait_selector: str, timeout: int = 15000, proxy: str | None = None,
) -> str | None:
    """Navega até a URL, espera o seletor, retorna o HTML. Retorna None se falhar."""
    try:
        async with stealth_page(proxy=proxy) as page:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(wait_selector, timeout=timeout)
            return await page.content()
    except Exception as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_browser_proxy.py -v`
Expected: all 2 PASS

**Step 5: Commit**

```
feat: add proxy parameter to browser.py stealth functions
```

---

### Task 3: BNESpider proxy integration

**Files:**
- Modify: `src/vagas/spiders/bne.py:12` (change import from `stealth_page` to `stealth_context`)
- Modify: `src/vagas/spiders/bne.py:221-277` (`_crawl_search` — add `_record_failure`/`_record_success` at real failure points)
- Modify: `src/vagas/spiders/bne.py:279-333` (`crawl` — restructure to support browser restart)

**Step 1: Understand the BNE-specific challenge**

BNE uses `page.evaluate(fetch(...))` inside the browser to keep Cloudflare/GoCache cookies. If we restart the browser (e.g., when proxy activates), the new page has no cookies. We must navigate to a BNE URL after restart to re-acquire cookies.

Failure tracking goes inside `_crawl_search` at actual failure points (navigation blocked, FilterKey missing, API error) — NOT based on empty return value (which can be legitimate).

**Step 2: Change import**

In `bne.py` line 12, change:
```python
from vagas.browser import stealth_context
```

**Step 3: Add failure tracking to `_crawl_search`**

Replace `_crawl_search` method (lines 221-277):

```python
async def _crawl_search(self, page, search_url: str, seen_ids: set[str]) -> list[Vaga]:
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

    self._record_success()
    filter_key = match.group(1)
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

        new = 0
        for v in page_vagas:
            eid = v.external_id or ""
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                vagas.append(v)
                new += 1

        if new == 0:
            break

        new_match = FILTER_KEY_RE.search(str(data))
        if new_match:
            filter_key = new_match.group(1)

        await asyncio.sleep(1)

    return vagas
```

**Step 4: Restructure `crawl` for browser restart**

Replace the `crawl` method (lines 279-333):

```python
async def crawl(self, known_ids: set[str] | None = None) -> list[Vaga]:
    seen_ids: set[str] = set()
    all_vagas: list[Vaga] = []

    ctx_manager = stealth_context(proxy=self._proxy)
    ctx = await ctx_manager.__aenter__()
    page = await ctx.new_page()
    browser_has_proxy = self._proxy is not None

    async def _restart_browser():
        nonlocal ctx_manager, ctx, page, browser_has_proxy
        log.info("[%s] restarting browser (proxy=%s)", self.name, bool(self._proxy))
        await ctx_manager.__aexit__(None, None, None)
        ctx_manager = stealth_context(proxy=self._proxy)
        ctx = await ctx_manager.__aenter__()
        page = await ctx.new_page()
        browser_has_proxy = self._proxy is not None
        # Re-acquire Cloudflare/GoCache cookies by visiting a BNE page
        try:
            await page.goto(SEARCH_PAGES[0], wait_until="domcontentloaded")
            await asyncio.sleep(3)
        except Exception:
            log.warning("[%s] failed to re-acquire cookies after restart", self.name)

    try:
        # 1. Crawl each search URL
        for search_url in SEARCH_PAGES:
            vagas = await self._crawl_search(page, search_url, seen_ids)
            # If proxy activated during _crawl_search, restart browser with proxy
            if self._proxy and not browser_has_proxy:
                await _restart_browser()
            all_vagas.extend(vagas)
            log.info("[%s] %s: %d new vagas (total: %d)",
                     self.name, search_url.split("/")[-1], len(vagas), len(all_vagas))
            await asyncio.sleep(random.uniform(2, 4))

        # 2. Fetch detail pages via fetch() inside browser
        _known = known_ids or set()
        need_detail = [v for v in all_vagas
                       if v.url and v.url != SEARCH_PAGE
                       and v.external_id not in _known]
        log.info("[%s] %d vagas need detail (%d already known)",
                 self.name, len(need_detail), len(all_vagas) - len(need_detail))

        fetched = 0
        consecutive_errors = 0
        max_retries = 3
        pause_count = 0
        for vaga in need_detail:
            try:
                detail_html = await page.evaluate(_FETCH_HTML_JS, vaga.url)
                if isinstance(detail_html, dict) and "error" in detail_html:
                    log.debug("[%s] detail error %s: %s", self.name, vaga.url, detail_html["error"])
                    consecutive_errors += 1
                    if self._record_failure():
                        await _restart_browser()
                        consecutive_errors = 0
                        continue
                    if consecutive_errors >= 3:
                        pause_count += 1
                        if pause_count >= max_retries:
                            log.warning("[%s] %d pause cycles reached, giving up on details",
                                        self.name, max_retries)
                            break
                        log.info("[%s] 3 consecutive errors, pausing 60s (%d/%d)",
                                 self.name, pause_count, max_retries)
                        await asyncio.sleep(60)
                        consecutive_errors = 0
                    continue
                consecutive_errors = 0
                pause_count = 0
                self._record_success()
                self.parse_detail(detail_html, vaga)
                fetched += 1
                log.debug("[%s] detail fetched: %s", self.name, vaga.url)
                await asyncio.sleep(3 + random.uniform(1, 2))
            except Exception as e:
                log.warning("[%s] detail failed %s: %s", self.name, vaga.url, e)

        log.info("[%s] details fetched: %d/%d", self.name, fetched, len(all_vagas))
    finally:
        await ctx_manager.__aexit__(None, None, None)

    log.info("[%s] crawl finished: %d vagas", self.name, len(all_vagas))
    return all_vagas
```

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS (existing BNE parse tests don't touch crawl)

**Step 6: Commit**

```
feat: integrate proxy fallback into BNESpider
```

---

### Task 4: IndeedSpider proxy integration

**Files:**
- Modify: `src/vagas/spiders/indeed.py:309-381` (crawl method)

**Step 1: Identify integration points**

Indeed already has `_restart_browser` logic and `consecutive_failures` tracking. Changes:
- `stealth_context()` → `stealth_context(proxy=self._proxy)`
- `_restart_browser` recreates with `stealth_context(proxy=self._proxy)`
- Hook `_record_failure()`/`_record_success()` into existing `_track_failures`

**Step 2: Implement Indeed proxy integration**

Replace the `crawl` method (lines 309-381):

```python
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

    consecutive_failures = 0
    context_manager = stealth_context(proxy=self._proxy)
    context = await context_manager.__aenter__()

    async def _restart_browser():
        nonlocal context, context_manager
        log.info("[%s] restarting browser (proxy=%s)", self.name, bool(self._proxy))
        await context_manager.__aexit__(None, None, None)
        context_manager = stealth_context(proxy=self._proxy)
        context = await context_manager.__aenter__()

    async def _track_failures(results):
        nonlocal consecutive_failures
        if not results:
            consecutive_failures += 1
            just_activated = self._record_failure()
            if just_activated or consecutive_failures >= 3:
                await _restart_browser()
                consecutive_failures = 0
        else:
            consecutive_failures = 0
            self._record_success()

    target_locations = locations or ["Brasil"]

    try:
        # 1. Specialty queries
        for loc in target_locations:
            for query in _SEARCH_QUERIES:
                results = await self._fetch_query(context, query, loc)
                _collect(results)
                await _track_failures(results)
                await asyncio.sleep(random.uniform(3, 6))

            log.info("[%s] after specialty queries for '%s': %d unique results",
                     self.name, loc, len(all_results))

        # 2. Broad "médico" query per city (skip when explicit locations provided)
        if not locations:
            for location in _LOCATION_FILTERS:
                results = await self._fetch_query(context, "médico", location)
                new = _collect(results)
                if new:
                    log.info("[%s] location '%s': %d new results", self.name, location, new)
                await _track_failures(results)
                await asyncio.sleep(random.uniform(3, 6))
    finally:
        await context_manager.__aexit__(None, None, None)

    log.info("[%s] total unique results: %d", self.name, len(all_results))
    return self.parse_mosaic(all_results)
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```
feat: integrate proxy fallback into IndeedSpider
```

---

### Task 5: VagasComSpider proxy integration

**Files:**
- Modify: `src/vagas/spiders/vagas_com.py:200-249` (crawl method)

**Step 1: Understand integration strategy**

VagasComSpider creates a new `stealth_page()` per search URL, so proxy activation naturally takes effect on the next URL. When proxy activates on a failed URL, we retry that URL once with the proxy. For the detail phase, the browser is created once with the current proxy state.

**Step 2: Implement VagasComSpider proxy integration**

Replace the `crawl` method (lines 200-249):

```python
async def crawl(self, known_ids: set[str] | None = None) -> list[Vaga]:
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
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```
feat: integrate proxy fallback into VagasComSpider
```

---

### Task 6: InfoJobsSpider proxy integration

**Files:**
- Modify: `src/vagas/spiders/infojobs.py:59-121` (crawl method)

**Step 1: Understand integration strategy**

InfoJobs creates a fresh `stealth_page()` per search query (like VagasCom), so proxy activation naturally takes effect on the next query. The httpx detail phase creates the client once with current proxy state.

**Step 2: Implement InfoJobs proxy integration**

Replace the `crawl` method (lines 59-121):

```python
async def crawl(self, known_ids: set[str] | None = None) -> list[Vaga]:
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
```

**Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```
feat: integrate proxy fallback into InfoJobsSpider
```

---

### Task 7: CLI proxy summary log

**Files:**
- Modify: `src/vagas/cli.py:48-136` (run function)

**Step 1: Add proxy activation tracking**

Add a `proxy_activated` list before the spider loop. After each spider's crawl (inside the try block), check `spider._proxy_active`. Log summary at the end.

Add `proxy_activated = []` before line 48 (`for spider_cls in spiders:`).

After `vagas = await spider.crawl(...)` (line 54), add:
```python
if spider._proxy_active:
    proxy_activated.append(spider.name)
```

Also in the `except Exception:` block (line 135), add the same check.

Before closing conn, add:
```python
if proxy_activated:
    log.info("Proxy activated for: %s", ", ".join(proxy_activated))
```

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 3: Commit**

```
feat: log proxy activation summary in CLI
```

---

### Task 8: Add PROXY_URL to .env

**Files:**
- Modify: `.env` (add PROXY_URL — this file is NOT committed, it contains secrets)

**Step 1: Add PROXY_URL to .env**

```
PROXY_URL=http://<user>:<password>@gate.decodo.com:10001
```

**No commit** — `.env` contains secrets.

---

### Task 9: Final integration test (manual)

**Step 1: Run all automated tests**

Run: `pytest tests/ -v`
Expected: all PASS

**Step 2: Run dry-run to verify everything works**

Run: `vagas --dry-run`
Expected: spiders run normally. If sites block, proxy activates and log shows it.

**Step 3: Final commit if any fixes needed**
