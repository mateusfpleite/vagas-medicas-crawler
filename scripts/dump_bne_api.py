"""Quick script to dump the raw JSON from BNE API — see all available fields."""

import asyncio
import json

from vagas.browser import stealth_page
from vagas.spiders.bne import BASE_URL, API_PATH, FILTER_KEY_RE, SEARCH_PAGES, _FETCH_API_JS


async def main():
    async with stealth_page() as page:
        url = SEARCH_PAGES[0]
        print(f"Opening {url} ...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        html = await page.content()
        match = FILTER_KEY_RE.search(html)
        if not match:
            print("Could not find FilterKey!")
            return

        filter_key = match.group(1)
        api_url = (
            f"{BASE_URL}{API_PATH}"
            f"?FilterKey=filterKey:{filter_key}"
            f"&NextPage=false&PrevPage=false"
        )
        print(f"Calling API: {api_url}\n")

        data = await page.evaluate(_FETCH_API_JS, api_url)
        if not data or "error" in data:
            print(f"API error: {data}")
            return

        items = data.get("data", {}).get("listVagas", [])
        print(f"Got {len(items)} items. First item:\n")
        if items:
            print(json.dumps(items[0], indent=2, ensure_ascii=False, default=str))


asyncio.run(main())
