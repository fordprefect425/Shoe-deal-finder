"""
debug_scrape.py
Run this to see the raw output from each scraper without any ranking filters.
Usage:
    python3 debug_scrape.py
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

CONFIG_PATH = os.path.join("data", "config.json")

async def main():
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    from scrapers.factory import get_scraper

    for shoe in config["tracked_shoes"]:
        print(f"\n{'='*60}")
        print(f"SHOE: {shoe['name']} | Size: {shoe.get('size')}")
        print(f"{'='*60}")

        for url_entry in shoe["urls"]:
            print(f"\n  Site: {url_entry['site_name']}")
            print(f"  URL:  {url_entry['product_url'][:80]}...")

            scraper = get_scraper(url_entry["site_name"], url_entry.get("site_type", "requests"))
            try:
                result = await scraper.scrape(url_entry["product_url"], size=shoe.get("size"))
                print(f"  Title:     {result.get('title')}")
                print(f"  Price:     {result.get('price')}")
                print(f"  In Stock:  {result.get('in_stock')}")
                print(f"  Size Avail:{result.get('size_available')}")
                print(f"  Error:     {result.get('error', 'None')}")
            except Exception as e:
                print(f"  ❌ EXCEPTION: {e}")

asyncio.run(main())
