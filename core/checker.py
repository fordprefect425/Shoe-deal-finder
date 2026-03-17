"""
core/checker.py
Main orchestration: run scrapers for all configured URLs, save snapshots,
rank deals, detect changes, and trigger Telegram notifications.
"""

import logging
from datetime import datetime
from typing import Optional

from core import storage, ranking, alerts
from scrapers.factory import get_scraper

logger = logging.getLogger(__name__)


async def check_url(shoe_config: dict, url_entry: dict) -> dict:
    """
    Run the appropriate scraper for a single URL entry.
    Returns a result dict (may contain 'error' key on failure).
    """
    site_type = url_entry.get("site_type", "requests")
    scraper = get_scraper(url_entry["site_name"], site_type)

    if scraper is None:
        from scrapers.generic import GenericScraper
        scraper = GenericScraper()

    try:
        result = await scraper.scrape(
            url=url_entry["product_url"],
            size=shoe_config.get("size"),
        )
        result["shoe_id"] = shoe_config["id"]
        result["product_url"] = url_entry["product_url"]
        result["site_name"] = url_entry["site_name"]
        result["checked_at"] = datetime.utcnow().isoformat()
        return result
    except Exception as exc:
        logger.error(
            "Scrape failed for %s (%s): %s",
            shoe_config["name"],
            url_entry["site_name"],
            exc,
            exc_info=True,
        )
        return {
            "shoe_id": shoe_config["id"],
            "site_name": url_entry["site_name"],
            "product_url": url_entry["product_url"],
            "error": str(exc),
            "in_stock": False,
            "checked_at": datetime.utcnow().isoformat(),
        }


async def run_check(config: dict, send_telegram_fn=None, force_summary: bool = False) -> list[dict]:
    """
    Full check run across all tracked shoes.

    Args:
        config: Parsed config.json content
        send_telegram_fn: async callable(chat_id, text) for notifications
        force_summary: If True, bypass "sent today" check for the summary message

    Returns:
        List of result dicts (one per shoe)
    """
    logger.info("=== Starting shoe price check run (force=%s) ===", force_summary)
    results = []

    for shoe in config.get("tracked_shoes", []):
        if not shoe.get("is_active", True):
            continue

        shoe_name = shoe["name"]
        shoe_id = shoe["id"]
        logger.info("Checking shoe: %s (size %s)", shoe_name, shoe.get("size"))

        all_offers = []

        for url_entry in shoe.get("urls", []):
            offer = await check_url(shoe, url_entry)
            all_offers.append(offer)

            if not offer.get("error"):
                storage.save_snapshot(offer)
            else:
                logger.warning(
                    "Skipping snapshot for %s — scrape error: %s",
                    url_entry["site_name"],
                    offer.get("error"),
                )

        # Rank valid offers
        best_offer = ranking.get_best_deal(all_offers)

        # Load previous best price for delta
        previous_price = _get_previous_best_price(shoe_id, shoe.get("urls", []))

        shoe_result = {
            "shoe_config": shoe,
            "best_offer": best_offer,
            "previous_price": previous_price,
            "all_offers": all_offers,
        }
        results.append(shoe_result)

        # Price-drop instant alert
        if send_telegram_fn and best_offer:
            if alerts.should_send_price_drop_alert(shoe, best_offer, previous_price):
                msg = alerts.format_price_drop_alert(shoe, best_offer, previous_price)
                msg_hash = alerts.get_message_hash(shoe_id, best_offer["price"])
                if not storage.was_alert_sent_today(shoe_id, "price_drop", msg_hash):
                    chat_id = config["telegram"]["chat_id"]
                    await send_telegram_fn(chat_id, msg)
                    storage.log_alert(shoe_id, "price_drop", msg_hash)
                    logger.info("Sent price-drop alert for %s", shoe_name)

    # Daily summary
    if send_telegram_fn and results:
        summary = alerts.format_daily_summary(results)
        chat_id = config["telegram"]["chat_id"]
        
        # Use a more specific hash for the summary (based on number of shoes + best prices)
        prices_sum = sum(r["best_offer"]["price"] for r in results if r.get("best_offer"))
        summary_hash = alerts.get_message_hash("summary_v1", prices_sum + float(len(results)))
        
        if force_summary or not storage.was_alert_sent_today("summary", "daily", summary_hash):
            await send_telegram_fn(chat_id, summary)
            storage.log_alert("summary", "daily", summary_hash)
            logger.info("Sent daily summary to Telegram")

    logger.info("=== Check run complete (%d shoes processed) ===", len(results))
    return results


def _get_previous_best_price(shoe_id: str, url_entries: list) -> Optional[float]:
    """
    Load the most recent price for each URL, run ranking on those,
    and return the best previous price (if any).
    """
    prev_snapshots = []
    for url_entry in url_entries:
        snap = storage.get_last_snapshot(shoe_id, url_entry["product_url"])
        if snap and snap.get("price"):
            prev_snapshots.append({
                "price": snap["price"],
                "in_stock": bool(snap.get("in_stock")),
                "size_available": snap.get("size_available"),
                "site_name": snap.get("site_name"),
                "product_url": snap.get("product_url"),
            })

    best = ranking.get_best_deal(prev_snapshots)
    return best["price"] if best else None
