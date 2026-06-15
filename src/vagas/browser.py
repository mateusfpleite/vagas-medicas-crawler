import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

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


_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

_BLOCKED_DOMAINS = {
    "www.googletagmanager.com",
    "googletagmanager.com",
    "posthog.bne.com.br",
    "scripts.clarity.ms",
    "www.clarity.ms",
    "c03.s3.indeed.com",
}


@asynccontextmanager
async def stealth_context(
    headless: bool = True,
    proxy: str | None = None,
    block_resources: bool = False,
):
    """Abre um browser Playwright com stealth e retorna um BrowserContext.

    Args:
        block_resources: Block images, CSS, fonts and media to save bandwidth.
    """
    async with async_playwright() as p:
        launch_opts: dict = {"headless": headless}
        if proxy:
            parsed = urlparse(proxy)
            proxy_opts: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
            if parsed.username:
                proxy_opts["username"] = parsed.username
            if parsed.password:
                proxy_opts["password"] = parsed.password
            launch_opts["proxy"] = proxy_opts
        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        await _stealth.apply_stealth_async(context)

        async def _route_handler(route):
            url_hostname = urlparse(route.request.url).hostname or ""
            if url_hostname in _BLOCKED_DOMAINS:
                await route.abort()
            elif block_resources and route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", _route_handler)

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
