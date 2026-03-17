"""
core/alerts.py
Change detection logic and Telegram message formatting.
"""

import hashlib
import logging
from typing import Optional

from core.ranking import compute_delta, compute_drop_percent

logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def should_send_price_drop_alert(
    shoe_config: dict,
    current_best: Optional[dict],
    previous_best_price: Optional[float],
) -> bool:
    """
    Returns True if a price-drop alert should be fired.
    Conditions (any one sufficient):
      - Price dropped below user's target_price
      - Price dropped by >= alert_drop_percent from last known price
    """
    if not current_best or current_best.get("price") is None:
        return False

    price = current_best["price"]
    target = shoe_config.get("target_price")
    threshold = shoe_config.get("alert_drop_percent", 5)

    if target and price <= target:
        logger.info("Price %s is at or below target %s for %s", price, target, shoe_config["name"])
        return True

    drop_pct = compute_drop_percent(price, previous_best_price)
    if drop_pct and drop_pct >= threshold:
        logger.info("Price dropped %.1f%% for %s", drop_pct, shoe_config["name"])
        return True

    return False


def format_daily_summary(shoe_results: list[dict]) -> str:
    """
    Build the Telegram markdown message for the daily summary.
    shoe_results: list of {shoe_config, best_offer, previous_price, all_offers}
    """
    lines = ["🥾 *Daily Shoe Deal Update*\n"]

    for result in shoe_results:
        shoe = result["shoe_config"]
        best = result.get("best_offer")
        prev_price = result.get("previous_price")
        name = shoe["name"]
        size = shoe.get("size", "?")

        lines.append(f"━━━━━━━━━━━━━━━━")
        lines.append(f"👟 *{name}* — Size {size}")

        if not best:
            lines.append("❌ No valid offers found today")
            lines.append("")
            continue

        price = best["price"]
        site = best.get("site_name", "Unknown")
        url = best.get("product_url", "")
        in_stock = best.get("in_stock", False)

        price_str = f"₹{price:,.0f}"
        lines.append(f"💰 Best: *{price_str}* on {site}")

        if prev_price and prev_price != price:
            delta = compute_delta(price, prev_price)
            if delta < 0:
                lines.append(f"📉 Was: ₹{prev_price:,.0f} → Saved ₹{abs(delta):,.0f}")
            else:
                lines.append(f"📈 Was: ₹{prev_price:,.0f} → Up ₹{delta:,.0f}")
        elif prev_price == price:
            lines.append(f"↔️ No change from ₹{prev_price:,.0f}")

        stock_str = "✅ In stock" if in_stock else "❌ Out of stock"
        lines.append(f"📦 Status: {stock_str}")

        target = shoe.get("target_price")
        if target:
            if price <= target:
                lines.append(f"🎯 *Below your target of ₹{target:,.0f}!*")
            else:
                lines.append(f"🎯 Target: ₹{target:,.0f} (₹{price - target:,.0f} away)")

        if url:
            lines.append(f"🔗 [View Deal]({url})")

        lines.append("")

    return "\n".join(lines)


def format_price_drop_alert(shoe: dict, current_best: dict, previous_price: Optional[float]) -> str:
    """Build an urgent price-drop alert message."""
    name = shoe["name"]
    size = shoe.get("size", "?")
    price = current_best["price"]
    site = current_best.get("site_name", "Unknown")
    url = current_best.get("product_url", "")

    lines = [
        "🔥 *Price Drop Alert!*\n",
        f"👟 *{name}* — Size {size}",
        f"💰 Now: *₹{price:,.0f}*",
    ]

    if previous_price:
        saved = previous_price - price
        lines.append(f"📉 Earlier: ₹{previous_price:,.0f}")
        lines.append(f"✂️ Savings: ₹{saved:,.0f}")

    target = shoe.get("target_price")
    if target and price <= target:
        lines.append(f"🎯 *At or below your target price of ₹{target:,.0f}!*")

    lines.append(f"🛒 Store: {site}")
    if url:
        lines.append(f"🔗 [Buy Now]({url})")

    return "\n".join(lines)


def get_message_hash(shoe_id: str, price: float) -> str:
    return _hash(f"{shoe_id}:{price:.2f}")
