"""
core/ranking.py
Deal comparison and best-deal selection logic.
"""

from typing import Optional


def rank_offers(offers: list[dict]) -> list[dict]:
    """
    Filter and sort offers to find the best deals.

    Rules (from spec §13):
    1. Ignore offers with scraping errors (no price)
    2. Ignore out-of-stock offers
    3. Ignore offers where size is confirmed unavailable
    4. Sort by lowest price ascending
    """
    valid = []
    for offer in offers:
        if offer.get("error"):
            continue
        if offer.get("price") is None:
            continue
        if not offer.get("in_stock", False):
            continue
        # size_available: True = OK, False = skip, None/-1 = unknown (allow)
        size_avail = offer.get("size_available")
        if size_avail is False:
            continue
        valid.append(offer)

    valid.sort(key=lambda o: o["price"])
    return valid


def get_best_deal(offers: list[dict]) -> Optional[dict]:
    """Return the cheapest valid offer, or None if none are valid."""
    ranked = rank_offers(offers)
    return ranked[0] if ranked else None


def compute_delta(current_price: float, last_price: Optional[float]) -> Optional[float]:
    """
    Return the price change (negative = drop, positive = rise).
    Returns None if last_price is unavailable.
    """
    if last_price is None or last_price == 0:
        return None
    return current_price - last_price


def compute_drop_percent(current_price: float, last_price: Optional[float]) -> Optional[float]:
    """Return the percentage drop (positive number means a decrease)."""
    if last_price is None or last_price == 0:
        return None
    return ((last_price - current_price) / last_price) * 100
