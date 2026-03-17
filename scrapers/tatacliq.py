"""
scrapers/tatacliq.py
Tata CLiQ product page scraper using Playwright.
"""

import logging
from datetime import datetime
from typing import Optional

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--lang=en-IN",
]


class TataCliqScraper(BaseScraper):
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=STEALTH_ARGS,
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-IN",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                },
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await ctx.new_page()
            try:
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                title = await self._extract_title(page)
                price = await self._extract_price(page)
                in_stock, size_available = await self._check_stock(page, size)

                return {
                    "site_name": "TataCliq",
                    "title": title,
                    "price": price,
                    "currency": "INR",
                    "in_stock": in_stock,
                    "size_available": size_available,
                    "product_url": url,
                    "checked_at": datetime.utcnow().isoformat(),
                }
            finally:
                await browser.close()

    async def _extract_title(self, page) -> Optional[str]:
        selectors = ["h1.ProductTitle, h1.pdp-title, h1"]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    return (await el.inner_text(timeout=5000)).strip()
            except Exception:
                continue
        return None

    async def _extract_price(self, page) -> Optional[float]:
        selectors = [
            ".pdp-selling-price",
            ".ProductPrice-selling",
            ".price-offer",
            "span[class*='sellingPrice']",
            "span[class*='SalePrice']",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text(timeout=3000)
                    price = self._clean_price(text)
                    if price:
                        return price
            except Exception:
                continue
        return None

    async def _check_stock(self, page, size: Optional[str]):
        in_stock = True
        size_available = None

        try:
            oos = page.locator("[class*='OutOfStock'], [class*='sold-out'], .notify-me-btn")
            if await oos.count() > 0:
                in_stock = False
                return False, False
        except Exception:
            pass

        if size:
            try:
                size_btn = page.locator(
                    f"[data-size='{size}'], "
                    f"li.size-item:has-text('{size}'), "
                    f"button:has-text('{size}')"
                )
                if await size_btn.count() > 0:
                    classes = await size_btn.first.get_attribute("class") or ""
                    aria_disabled = await size_btn.first.get_attribute("aria-disabled") or ""
                    if any(w in classes for w in ["disabled", "unavailable", "out-of-stock"]) \
                            or aria_disabled == "true":
                        size_available = False
                    else:
                        size_available = True
            except Exception:
                size_available = None

        return in_stock, size_available
