"""
scrapers/puma.py
Puma India product page scraper using Playwright with stealth settings.
"""

import logging
import re
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


class PumaScraper(BaseScraper):
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
                await page.goto(url, timeout=40_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                title = await self._extract_title(page)
                price = await self._extract_price(page)
                in_stock, size_available = await self._check_stock(page, size)

                logger.info(
                    "Puma %s: title=%s price=%s in_stock=%s",
                    url[:60], title, price, in_stock
                )

                return {
                    "site_name": "Puma",
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
        selectors = ["h1.product-name", "h1.pdp-title", "h1"]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = (await el.inner_text(timeout=5000)).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    async def _extract_price(self, page) -> Optional[float]:
        selectors = [
            ".pdp-discounted-price",
            ".pdp-price",
            ".price__sale .price-item--sale",
            "span.price-group",
            "[data-selling-price]",
            ".product-price--sale",
            ".price-value",
            "[class*='discounted']",
            "[class*='selling']",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text(timeout=3000)
                    price = self._clean_price(text)
                    if price and price > 100:
                        return price
            except Exception:
                continue

        # Fallback: scan HTML for JSON price data
        try:
            content = await page.content()
            matches = re.findall(
                r'["\'](?:price|sellingPrice|salePrice|discountedPrice)["\']:\s*["\']?(\d{3,6})',
                content
            )
            if matches:
                prices = [float(m) for m in matches if float(m) > 100]
                if prices:
                    return min(prices)
        except Exception:
            pass

        return None

    async def _check_stock(self, page, size: Optional[str]):
        in_stock = True
        size_available = None

        try:
            oos_el = page.locator(".notify-me, .sold-out, [data-out-of-stock='true'], .out-of-stock")
            if await oos_el.count() > 0:
                in_stock = False
                return False, False
        except Exception:
            pass

        if size:
            try:
                size_btn = page.locator(
                    f"button.size-tile:has-text('{size}'), "
                    f"[data-size='{size}'], "
                    f"li.size:has-text('{size}')"
                )
                if await size_btn.count() > 0:
                    classes = await size_btn.first.get_attribute("class") or ""
                    disabled = await size_btn.first.get_attribute("disabled")
                    if "unavailable" in classes or "disabled" in classes or disabled is not None:
                        size_available = False
                    else:
                        size_available = True
            except Exception:
                size_available = None

        return in_stock, size_available
