"""
scrapers/base.py
Abstract base class defining the scraper contract.
"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseScraper(ABC):
    """
    All site scrapers must implement this interface.

    scrape() must return a dict matching this shape:
    {
        "site_name": str,
        "title": str | None,
        "price": float | None,
        "currency": str,          # default "INR"
        "in_stock": bool,
        "size_available": bool | None,
        "product_url": str,
        "checked_at": str,        # ISO 8601 UTC
    }
    On failure, raise an exception — checker.py will catch it.
    """

    @abstractmethod
    async def scrape(self, url: str, size: Optional[str] = None) -> dict:
        ...

    # ------------------------------------------------------------------
    # Utility helpers available to subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_price(text: str) -> Optional[float]:
        """Parse ₹6,499 → 6499.0 or None on failure."""
        if not text:
            return None
        cleaned = text.replace("₹", "").replace(",", "").replace("\xa0", "").strip()
        # Remove non-numeric except dot
        import re
        match = re.search(r"\d[\d.]*", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None
