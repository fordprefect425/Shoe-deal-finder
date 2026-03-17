"""
scrapers/myntra.py
Myntra product page scraper using Playwright with stealth settings.
Myntra is a heavily JS-rendered SPA with anti-bot measures.
"""

import logging
import asyncio
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
    "--disable-web-security",
    "--lang=en-IN",
]


class MyntraScraper(BaseScraper):
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        from playwright.async_api import async_playwright

        import random
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=STEALTH_ARGS,
            )
            ctx = await browser.new_context(
                user_agent=random.choice(user_agents),
                locale="en-IN",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24"',
                    "sec-ch-ua-platform": '"Windows"',
                    "Referer": "https://www.google.com/",
                },
            )
            # Enhanced Stealth: Mask various fingerprints
            await ctx.add_init_script("""
                // Mask WebGL
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Open Source Technology Center';
                    if (parameter === 37446) return 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)';
                    return getParameter(parameter);
                };
                // Mask Canvas
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type) {
                    if (type === 'image/png' && this.width === 400 && this.height === 200) {
                        return originalToDataURL.apply(this, arguments); 
                    }
                    return originalToDataURL.apply(this, arguments);
                };
                // Mask Webdriver (already done but extra check)
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Languages
                Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en-US', 'en']});
            """)
            page = await ctx.new_page()
            try:
                # Add a small random jitter before navigation
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
                # Navigate initially to homepage to build some session context
                try:
                    await page.goto("https://www.myntra.com/", timeout=30_000, wait_until="domcontentloaded")
                    await asyncio.sleep(random.uniform(1, 2))
                except: pass

                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(random.randint(5000, 8000))

                # Human-like interaction: Scroll
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(random.uniform(1, 2))
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(2000)

                # Check if we hit the "Oops" page
                content_text = (await page.inner_text("body")).lower()
                if "oops! something went wrong" in content_text or "access denied" in content_text:
                    logger.warning("Myntra bot detection triggered for %s", url)
                    return {"error": "Bot detected (Oops page)", "product_url": url}


                title = await self._extract_title(page)
                price = await self._extract_price(page)
                in_stock, size_available = await self._check_stock(page, size)

                logger.info(
                    "Myntra %s: title=%s price=%s in_stock=%s",
                    url[:60], title, price, in_stock
                )

                return {
                    "site_name": "Myntra",
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
        selectors = [
            "h1.pdp-title",
            "h1.pdp-name",
            ".pdp-product-description-content h1",
            "h1",
        ]
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
            "span.pdp-price strong",
            "span.pdp-mrp strong",
            ".pdp-price",
            "span.pdp-discounted-price",
            "div.pdp-price-info",
            "[class*='pdp-price']",
            "[class*='sellingPrice']",
            "[class*='selling-price']",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    text = await el.inner_text(timeout=3000)
                    price = self._clean_price(text)
                    if price and price > 100:  # sanity check
                        return price
            except Exception:
                continue

        # Fallback: scan page text for price-like patterns
        try:
            content = await page.content()
            import re
            matches = re.findall(r'["\'](?:price|sellingPrice|discountedPrice)["\']:\s*["\']?(\d{3,6})', content)
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
            page_text = (await page.inner_text("body")).lower()
            if any(p in page_text for p in ["notify me when available", "sold out", "out of stock"]):
                # Only mark out of stock if there's also no price visible
                price_el = page.locator("span.pdp-price, [class*='pdp-price']").first
                if await price_el.count() == 0:
                    in_stock = False
                    return False, False
        except Exception:
            pass

        if size:
            try:
                size_btn = page.locator(
                    f"button.size-btn:has-text('{size}'), "
                    f"div.size-buttons-container button:has-text('{size}')"
                )
                if await size_btn.count() > 0:
                    classes = await size_btn.first.get_attribute("class") or ""
                    if "size-btn-out-of-stock" in classes or "is-out-of-stock" in classes:
                        size_available = False
                    else:
                        size_available = True
            except Exception:
                size_available = None

        return in_stock, size_available
