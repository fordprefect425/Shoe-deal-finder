"""
scrapers/factory.py
Returns the appropriate scraper instance based on site name / type.
"""

from typing import Optional
from scrapers.base import BaseScraper


SITE_MAP = {
    "puma": "scrapers.puma.PumaScraper",
    "myntra": "scrapers.myntra.MyntraScraper",
    "amazon": "scrapers.amazon.AmazonScraper",
    "tatacliq": "scrapers.tatacliq.TataCliqScraper",
    "tata cliq": "scrapers.tatacliq.TataCliqScraper",
}


def get_scraper(site_name: str, site_type: str = "requests") -> Optional[BaseScraper]:
    """
    Resolve and instantiate the correct scraper for a given site.

    Falls back to GenericScraper when no specific scraper exists.
    """
    key = site_name.lower().strip()
    class_path = SITE_MAP.get(key)

    if class_path:
        module_path, class_name = class_path.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()

    # Fallback: generic scrapers
    if site_type == "playwright":
        from scrapers.playwright_generic import PlaywrightGenericScraper
        return PlaywrightGenericScraper()
    
    from scrapers.generic import GenericScraper
    return GenericScraper()
