"""Quick test: verify Decodo proxy IP rotation via session ID changes.

Usage:
    python scripts/test_proxy_rotation.py

Requires PROXY_URL in .env (e.g. http://user:pass@gate.decodo.com:10001)
"""

import asyncio
import os
import random
import string
import sys
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

load_dotenv()

PROXY_URL = os.environ.get("PROXY_URL")
if not PROXY_URL:
    print("ERROR: PROXY_URL not set in .env")
    sys.exit(1)

IP_CHECK_URL = "https://httpbin.org/ip"
BNE_DETAIL_URL = "https://www.bne.com.br/vaga-de-emprego-na-area-Saude-em-SaoPaulo-SP/medico/5754325"

_stealth = Stealth()


def _make_session_proxy(base_url: str, session_id: str) -> str:
    """Build proxy URL with Decodo session parameter.

    Decodo format: user-PROXYUSER-session-XXX:password@host:port
    """
    parsed = urlparse(base_url)
    new_user = f"user-{parsed.username}-session-{session_id}"
    netloc = f"{new_user}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _swap_port(base_url: str, port: int) -> str:
    """Change the port in the proxy URL."""
    parsed = urlparse(base_url)
    netloc = f"{parsed.username}:{parsed.password}@{parsed.hostname}:{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _proxy_opts(proxy_url: str) -> dict:
    parsed = urlparse(proxy_url)
    opts: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        opts["username"] = parsed.username
    if parsed.password:
        opts["password"] = parsed.password
    return opts


async def check_ip(proxy_url: str, label: str, timeout: int = 30000) -> str | None:
    """Launch a browser with the given proxy and fetch our external IP."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy=_proxy_opts(proxy_url),
        )
        context = await browser.new_context()
        await _stealth.apply_stealth_async(context)
        page = await context.new_page()
        try:
            await page.goto(IP_CHECK_URL, wait_until="domcontentloaded", timeout=timeout)
            text = await page.inner_text("body")
            ip = text.strip()
            print(f"  [{label}] IP = {ip}")
            return ip
        except Exception as e:
            print(f"  [{label}] FAILED: {e}")
            return None
        finally:
            await browser.close()


async def fetch_bne(proxy_url: str, label: str, timeout: int = 45000) -> int | None:
    """Fetch a BNE detail page, return HTTP status."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy=_proxy_opts(proxy_url),
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        await _stealth.apply_stealth_async(context)
        page = await context.new_page()
        try:
            resp = await page.goto(BNE_DETAIL_URL, wait_until="domcontentloaded", timeout=timeout)
            status = resp.status if resp else None
            title = await page.title()
            print(f"  [{label}] HTTP {status} | title: {title[:60]}")
            return status
        except Exception as e:
            print(f"  [{label}] FAILED: {e}")
            return None
        finally:
            await browser.close()


def _rand_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


async def main():
    # ---- Test 1: BNE via base proxy (no session) ----
    print("=" * 60)
    print("Test 1: BNE detail via BASE proxy (port 10001, no session)")
    print("=" * 60)
    print()
    status = await fetch_bne(PROXY_URL, "base-proxy")
    print()

    # ---- Test 2: BNE via rotating port 7000 ----
    print("=" * 60)
    print("Test 2: BNE detail via ROTATING proxy (port 7000)")
    print("=" * 60)
    print()
    rotating_proxy = _swap_port(PROXY_URL, 7000)
    status = await fetch_bne(rotating_proxy, "rotating-7000")
    print()

    # ---- Test 3: BNE via session proxy (try 3 different sessions) ----
    print("=" * 60)
    print("Test 3: BNE detail via SESSION proxy (3 attempts, port 10001)")
    print("=" * 60)
    print()
    for i in range(3):
        session_id = _rand_id()
        proxy = _make_session_proxy(PROXY_URL, session_id)
        print(f"  Session: {session_id}")
        status = await fetch_bne(proxy, f"session-{i+1}")
        if status == 200:
            print("  -> OK! Session proxy works for BNE")
            break
        print()

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
