"""
scrapers/amazon.py
Amazon India product page scraper using requests + BeautifulSoup.
"""

import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class AmazonScraper(BaseScraper):
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        title = self._extract_title(soup)
        price = self._extract_price(soup)
        in_stock = self._check_stock(soup)

        return {
            "site_name": "Amazon",
            "title": title,
            "price": price,
            "currency": "INR",
            "in_stock": in_stock,
            "size_available": None,  # Amazon size check requires session/variant selection
            "product_url": url,
            "checked_at": datetime.utcnow().isoformat(),
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        el = soup.find("span", id="productTitle")
        if el:
            return el.get_text(strip=True)
        return None

    def _extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        # Priority order for Amazon price elements
        selectors = [
            ("span", {"class": "a-price-whole"}),
            ("span", {"id": "priceblock_ourprice"}),
            ("span", {"id": "priceblock_dealprice"}),
            ("span", {"class": "a-offscreen"}),
        ]
        for tag, attrs in selectors:
            el = soup.find(tag, attrs)
            if el:
                price = self._clean_price(el.get_text())
                if price:
                    return price

        # Try the apex price block
        apex = soup.find("div", {"id": "apex_offerDisplay_desktop"})
        if apex:
            price_el = apex.find("span", class_="a-price-whole")
            if price_el:
                price = self._clean_price(price_el.get_text())
                if price:
                    return price

        return None

    def _check_stock(self, soup: BeautifulSoup) -> bool:
        avail = soup.find("div", {"id": "availability"})
        if avail:
            text = avail.get_text(strip=True).lower()
            if any(p in text for p in ["out of stock", "unavailable", "currently unavailable"]):
                return False
            if "in stock" in text:
                return True

        # If we got a price, likely in stock
        return True
