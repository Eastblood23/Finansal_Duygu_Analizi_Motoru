import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, insert, select, func

from app.api.portfolio_routes import PortfolioInput
from app.models import NewsItem
from app.services.market_service import fetch_ticker_data
from app.services.portfolio_service import build_portfolio_report
from app.services.sentiment_service import signed_sentiment_expression


def holding(symbol, amount):
    return SimpleNamespace(symbol=symbol, amount=amount)


class PortfolioTests(unittest.TestCase):
    def test_usd_btc_and_gold_use_existing_units_and_one_currency(self):
        report = build_portfolio_report(
            [holding("USD_TRY", 100), holding("BTC", 0.1), holding("GOLD", 2)],
            {"USD_TRY": {"price": 40}, "BTC": {"price": 50000}, "GOLD": {"price": 3000}},
            {"GENERAL": -0.8, "CRYPTO": 0.8},
        )
        self.assertEqual(report["total_value_usd"], 11100)
        self.assertEqual(report["total_value_try"], 444000)
        self.assertEqual(report["items"][0]["value"], 100)
        self.assertAlmostEqual(report["sentiment_score"], (6100 * -0.8 + 5000 * 0.8) / 11100)

    def test_missing_price_does_not_become_zero_or_partial_total(self):
        report = build_portfolio_report(
            [holding("USD_TRY", 100), holding("BTC", 1)],
            {"USD_TRY": {"price": 40}, "BTC": {"price": None, "available": False}},
            {"GENERAL": 0.9},
        )
        self.assertIsNone(report["total_value_usd"])
        self.assertIsNone(report["total_value_try"])
        self.assertIsNone(report["sentiment_score"])
        self.assertEqual(report["known_value_usd"], 100)
        self.assertIsNone(report["items"][1]["value"])

    def test_bist_is_not_valued_as_dollars_and_record_is_preserved(self):
        report = build_portfolio_report([holding("BIST100", 3)], {"BIST100": {"price": 12000}}, {})
        self.assertIsNone(report["total_value_usd"])
        self.assertEqual(report["items"][0]["amount"], 3)
        self.assertEqual(report["items"][0]["valuation_status"], "unsupported_asset")

    def test_missing_fx_does_not_prevent_usd_valuation_or_invent_try(self):
        report = build_portfolio_report([holding("USD_TRY", 100)], {}, {})
        self.assertEqual(report["total_value_usd"], 100)
        self.assertIsNone(report["total_value_try"])
        self.assertIsNone(report["sentiment_score"])

    def test_no_news_is_distinct_from_neutral_and_coverage_is_explicit(self):
        items = [holding("USD_TRY", 100), holding("BTC", 1)]
        market = {"BTC": {"price": 100}}
        report = build_portfolio_report(items, market, {"GENERAL": 0})
        self.assertEqual(report["sentiment_score"], 0)
        self.assertEqual(report["sentiment_coverage"], 0.5)
        self.assertIsNone(build_portfolio_report(items, market, {})["sentiment_score"])

    def test_empty_portfolio_and_decimal_arithmetic(self):
        self.assertEqual(build_portfolio_report([], {}, {})["total_value_usd"], 0)
        report = build_portfolio_report([holding("BTC", 0.1)], {"BTC": {"price": 0.2}}, {})
        self.assertEqual(report["total_value_usd"], 0.02)

    def test_invalid_amounts_are_rejected(self):
        for amount in (-1, 1e100, float("nan"), float("inf"), float("-inf")):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                PortfolioInput(symbol="BTC", amount=amount)
        self.assertEqual(PortfolioInput(symbol="BTC", amount=0).amount, 0)

    def test_signed_sql_handles_negative_neutral_and_invalid_confidence(self):
        engine = create_engine("sqlite://")
        try:
            NewsItem.__table__.create(engine)
            with engine.begin() as conn:
                conn.execute(insert(NewsItem), [
                    {"sentiment_label": "positive", "sentiment_score": 0.9},
                    {"sentiment_label": "negative", "sentiment_score": 0.8},
                    {"sentiment_label": "neutral", "sentiment_score": 0.99},
                    {"sentiment_label": "positive", "sentiment_score": 2},
                    {"sentiment_label": "unknown", "sentiment_score": 0.9},
                ])
                score = conn.execute(select(func.avg(signed_sentiment_expression()))).scalar_one()
                self.assertAlmostEqual(score, (0.9 - 0.8 + 0) / 3)
        finally:
            engine.dispose()


class MarketFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_network_failure_is_explicitly_unavailable(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("test timeout")):
            result = await fetch_ticker_data("BTC", "BTC-USD")
        self.assertIsNone(result["price"])
        self.assertFalse(result["available"])
        self.assertIsNone(result["change_pct"])


if __name__ == "__main__":
    unittest.main()
