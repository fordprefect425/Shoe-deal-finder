"""
scrapers/playwright_generic.py
A generic scraper using Playwright for sites that block simple requests 
(like Adidas India) or require JS rendering.
"""

import logging
import random
import asyncio
from datetime import datetime
from typing import Optional

from scrapers.base import BaseScraper
from scrapers.generic import GenericScraper  # For selectors and cleaning

logger = logging.getLogger(__name__)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]

class PlaywrightGenericScraper(BaseScraper):
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=STEALTH_ARGS)
            # Use a realistic user agent
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            
            ctx = await browser.new_context(
                user_agent=ua,
                locale="en-IN",
                viewport={"width": 1440, "height": 900},
            )
            # Mask webdriver
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await ctx.new_page()
            try:
                # Add jitter
                await asyncio.sleep(random.uniform(1, 2))
                await page.goto(url, timeout=60_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)

                # Use the logic from GenericScraper but adapted for Playwright
                # We can grab the HTML and pass it to a helper or just use selectors.
                content = await page.content()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, "lxml")
                
                # We reuse the logic from GenericScraper by instantiating it internally
                gen = GenericScraper()
                title = gen._extract_title(soup)
                price = gen._extract_price(soup, content)
                in_stock = gen._check_stock(soup)
                
                # Check size if provided
                size_available = None
                if size:
                    # Simple check: is the size text present and not greyed out?
                    # This is very generic and might over-report.
                    page_text = (await page.inner_text("body")).lower()
                    if size.lower() in page_text:
                        size_available = True

                logger.info("PlaywrightGeneric %s: title=%s price=%s", url[:60], title, price)

                return {
                    "site_name": "Generic-PW",
                    "title": title,
                    "price": price,
                    "currency": "INR",
                    "in_stock": in_stock,
                    "size_available": size_available,
                    "product_url": url,
                    "checked_at": datetime.utcnow().isoformat(),
                }
            except Exception as e:
                logger.error("PlaywrightGeneric error for %s: %s", url, e)
                return {"error": str(e), "product_url": url}
            finally:
                await browser.close()
