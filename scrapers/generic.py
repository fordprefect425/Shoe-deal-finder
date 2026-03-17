"""
scrapers/generic.py
Generic scraper using requests + BeautifulSoup.
Attempts common price selectors / JSON-LD structured data.
"""

import json
import logging
import re
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 20  # seconds

# Common CSS selectors tried in order
PRICE_SELECTORS = [
    "[data-price]",
    ".price-value",
    ".product-price",
    ".selling-price",
    ".pdp-price",
    ".offer-price",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",   # Amazon
    ".discountedPrice",
    "span[itemprop='price']",
]

OUT_OF_STOCK_PHRASES = [
    "out of stock",
    "currently unavailable",
    "sold out",
    "not available",
    "notify me",
]


class GenericScraper(BaseScraper):
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        title = self._extract_title(soup)
        price = self._extract_price(soup, response.text)
        in_stock = self._check_stock(soup)

        return {
            "site_name": "Generic",
            "title": title,
            "price": price,
            "currency": "INR",
            "in_stock": in_stock,
            "size_available": None,
            "product_url": url,
            "checked_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        tag = soup.find("meta", property="og:title")
        if tag and tag.get("content"):
            return tag["content"].strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return None

    def _extract_price(self, soup: BeautifulSoup, raw_html: str) -> Optional[float]:
        # 1. Try JSON-LD structured data
        price = self._from_json_ld(soup)
        if price:
            return price

        # 2. Try og:price:amount meta tag
        meta_price = soup.find("meta", property="product:price:amount")
        if meta_price and meta_price.get("content"):
            return self._clean_price(meta_price["content"])

        # 3. Try common CSS selectors
        for selector in PRICE_SELECTORS:
            el = soup.select_one(selector)
            if el:
                text = el.get("content") or el.get("data-price") or el.get_text()
                price = self._clean_price(text)
                if price:
                    return price

        return None

    def _from_json_ld(self, soup: BeautifulSoup) -> Optional[float]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") in ("Product", "Offer"):
                            offers = item.get("offers") or item
                            if isinstance(offers, dict):
                                p = offers.get("price") or offers.get("lowPrice")
                                if p: return float(str(p).replace(",", ""))
                            elif isinstance(offers, list):
                                for offer in offers:
                                    p = offer.get("price")
                                    if p: return float(str(p).replace(",", ""))
                elif isinstance(data, dict):
                    if data.get("@type") in ("Product", "Offer"):
                        offers = data.get("offers") or data
                        if isinstance(offers, dict):
                            p = offers.get("price") or offers.get("lowPrice")
                            if p: return float(str(p).replace(",", ""))
            except Exception:
                continue
        return None

    def _check_stock(self, soup: BeautifulSoup) -> bool:
        # Default to True unless we find a strong OOS signal
        page_text = soup.get_text(separator=" ").lower()
        for phrase in OUT_OF_STOCK_PHRASES:
            if phrase in page_text:
                # Double check: if it says "out of stock" but we found a price, it might be a "similar products" section
                return False
        return True
