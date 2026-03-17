"""
tests/test_core.py
Unit tests for the core modules: ranking, alerts, storage.
Run with: pytest tests/ -v
"""

import os
import sys
import tempfile
import pytest

# Ensure the project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# -----------------------------------------------------------------------
# Ranking tests
# -----------------------------------------------------------------------

from core.ranking import rank_offers, get_best_deal, compute_delta, compute_drop_percent


def make_offer(price, in_stock=True, size_available=None, error=None):
    o = {
        "price": price,
        "in_stock": in_stock,
        "size_available": size_available,
        "site_name": "TestSite",
        "product_url": "https://example.com",
    }
    if error:
        o["error"] = error
        o["price"] = None
    return o


class TestRanking:
    def test_filters_out_of_stock(self):
        offers = [make_offer(1000, in_stock=False), make_offer(2000, in_stock=True)]
        result = rank_offers(offers)
        assert len(result) == 1
        assert result[0]["price"] == 2000

    def test_filters_error_offers(self):
        offers = [make_offer(None, error="Timeout"), make_offer(3000)]
        result = rank_offers(offers)
        assert len(result) == 1

    def test_filters_unavailable_size(self):
        offers = [
            make_offer(1500, size_available=False),
            make_offer(2500, size_available=True),
        ]
        result = rank_offers(offers)
        assert len(result) == 1
        assert result[0]["price"] == 2500

    def test_unknown_size_is_allowed(self):
        offers = [make_offer(1800, size_available=None)]
        result = rank_offers(offers)
        assert len(result) == 1

    def test_sorts_by_lowest_price(self):
        offers = [make_offer(5000), make_offer(3000), make_offer(4000)]
        result = rank_offers(offers)
        assert [o["price"] for o in result] == [3000, 4000, 5000]

    def test_get_best_deal_returns_cheapest(self):
        offers = [make_offer(8000), make_offer(5000), make_offer(6000)]
        best = get_best_deal(offers)
        assert best["price"] == 5000

    def test_get_best_deal_none_when_all_invalid(self):
        offers = [make_offer(1000, in_stock=False)]
        assert get_best_deal(offers) is None

    def test_compute_delta(self):
        assert compute_delta(4000, 5000) == -1000
        assert compute_delta(6000, 5000) == 1000

    def test_compute_delta_none_for_no_history(self):
        assert compute_delta(4000, None) is None

    def test_compute_drop_percent(self):
        pct = compute_drop_percent(4500, 5000)
        assert abs(pct - 10.0) < 0.01


# -----------------------------------------------------------------------
# Alerts tests
# -----------------------------------------------------------------------

from core.alerts import should_send_price_drop_alert, format_daily_summary


class TestAlerts:
    def test_alert_when_below_target(self):
        shoe = {"name": "Test Shoe", "id": "s1", "target_price": 5000, "alert_drop_percent": 10}
        best = {"price": 4500, "in_stock": True, "site_name": "Amazon", "product_url": "http://x"}
        assert should_send_price_drop_alert(shoe, best, 6000) is True

    def test_alert_when_drop_exceeds_threshold(self):
        shoe = {"name": "Test Shoe", "id": "s1", "target_price": None, "alert_drop_percent": 5}
        best = {"price": 4500, "in_stock": True, "site_name": "Amazon", "product_url": "http://x"}
        # 4500 vs 5000 = 10% drop > 5% threshold
        assert should_send_price_drop_alert(shoe, best, 5000) is True

    def test_no_alert_for_small_drop(self):
        shoe = {"name": "Test Shoe", "id": "s1", "target_price": None, "alert_drop_percent": 10}
        best = {"price": 4900, "in_stock": True, "site_name": "Amazon", "product_url": "http://x"}
        # 4900 vs 5000 = 2% drop < 10% threshold
        assert should_send_price_drop_alert(shoe, best, 5000) is False

    def test_no_alert_when_no_best(self):
        shoe = {"name": "Test Shoe", "id": "s1", "target_price": 3000, "alert_drop_percent": 5}
        assert should_send_price_drop_alert(shoe, None, 5000) is False

    def test_daily_summary_format(self):
        result = [
            {
                "shoe_config": {"id": "s1", "name": "Test Shoe", "size": "10", "target_price": None},
                "best_offer": {
                    "price": 4000,
                    "in_stock": True,
                    "site_name": "Puma",
                    "product_url": "http://example.com",
                },
                "previous_price": 4500,
                "all_offers": [],
            }
        ]
        summary = format_daily_summary(result)
        assert "Test Shoe" in summary
        assert "4,000" in summary or "4000" in summary

    def test_daily_summary_no_deal(self):
        result = [
            {
                "shoe_config": {"id": "s1", "name": "Ghost Shoe", "size": "9", "target_price": None},
                "best_offer": None,
                "previous_price": None,
                "all_offers": [],
            }
        ]
        summary = format_daily_summary(result)
        assert "Ghost Shoe" in summary
        assert "No valid offers" in summary


# -----------------------------------------------------------------------
# Storage tests
# -----------------------------------------------------------------------

import sqlite3
from datetime import datetime


class TestStorage:
    def setup_method(self):
        """Use an in-memory DB for each test."""
        # Monkey-patch DB_PATH to a temp file
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        import core.storage as st
        self._orig_path = st.DB_PATH
        st.DB_PATH = self.tmpfile.name
        st.init_db()

    def teardown_method(self):
        import core.storage as st
        st.DB_PATH = self._orig_path
        os.unlink(self.tmpfile.name)

    def test_save_and_retrieve_snapshot(self):
        import core.storage as st
        snap = {
            "shoe_id": "shoe_1",
            "site_name": "Puma",
            "product_url": "https://puma.com/shoe",
            "title": "Test Shoe",
            "price": 4999.0,
            "currency": "INR",
            "in_stock": True,
            "size_available": True,
            "checked_at": datetime.utcnow().isoformat(),
        }
        st.save_snapshot(snap)
        result = st.get_last_snapshot("shoe_1", "https://puma.com/shoe")
        assert result is not None
        assert result["price"] == 4999.0
        assert result["site_name"] == "Puma"

    def test_returns_none_for_missing(self):
        import core.storage as st
        result = st.get_last_snapshot("nonexistent", "http://nope.com")
        assert result is None

    def test_alert_deduplication(self):
        import core.storage as st
        st.log_alert("shoe_1", "price_drop", "abc123")
        assert st.was_alert_sent_today("shoe_1", "price_drop", "abc123") is True
        assert st.was_alert_sent_today("shoe_1", "price_drop", "different_hash") is False
