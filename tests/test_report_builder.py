import pandas as pd
import pytest
from app.services.report_builder import ReportBuilder


SWING_DF = pd.DataFrame([{"symbol": "RELIANCE", "score": 42.1}])
INTRADAY_DF = pd.DataFrame([{
    "symbol": "INFY", "score": 30.0, "volume_ratio": 2.5,
    "return_pct": 1.2, "breakout": True, "above_vwap": True,
}])


@pytest.fixture
def builder():
    return ReportBuilder()


class TestWatchlistPrompt:
    def test_contains_stock_symbol(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {})
        assert "RELIANCE" in prompt

    def test_contains_momentum_score(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {})
        assert "42.1" in prompt

    def test_injects_regime_and_vix(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {}, regime="BULL_HIGH_VIX", vix="22.5")
        assert "BULL_HIGH_VIX" in prompt
        assert "22.5" in prompt

    def test_no_regime_context_when_not_provided(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {})
        assert "Market regime" not in prompt

    def test_includes_news_headlines(self, builder):
        news = {"RELIANCE": ["Reliance Q4 profit beats estimates", "Oil refinery expansion"]}
        prompt = builder.build_watchlist_prompt(SWING_DF, news)
        assert "beats estimates" in prompt
        assert "Oil refinery" in prompt

    def test_requires_json_output(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {})
        assert "JSON" in prompt

    def test_bear_regime_hint_text(self, builder):
        prompt = builder.build_watchlist_prompt(SWING_DF, {}, regime="BEAR")
        assert "caution" in prompt.lower()


class TestIntradayPrompt:
    def test_contains_stock_symbol(self, builder):
        prompt = builder.build_intraday_prompt(INTRADAY_DF, {})
        assert "INFY" in prompt

    def test_contains_intraday_metrics(self, builder):
        prompt = builder.build_intraday_prompt(INTRADAY_DF, {})
        assert "Volume Ratio" in prompt
        assert "Breakout" in prompt
        assert "VWAP" in prompt

    def test_injects_regime_and_vix(self, builder):
        prompt = builder.build_intraday_prompt(INTRADAY_DF, {}, regime="BULL_LOW_VIX", vix="14.2")
        assert "BULL_LOW_VIX" in prompt
        assert "14.2" in prompt

    def test_includes_news_headlines(self, builder):
        news = {"INFY": ["Infosys wins $500M deal"]}
        prompt = builder.build_intraday_prompt(INTRADAY_DF, news)
        assert "$500M deal" in prompt


class TestRegimeContext:
    @pytest.mark.parametrize("regime,expected_hint", [
        ("BULL_HIGH_VIX", "defensive"),
        ("BULL_EXTREME_VIX", "strongest"),
        ("BULL_LOW_VIX", "freely"),
        ("BEAR", "caution"),
    ])
    def test_regime_hint_text(self, builder, regime, expected_hint):
        ctx = builder._regime_context(regime, "20.0")
        assert expected_hint in ctx.lower()

    def test_empty_string_when_no_regime(self, builder):
        assert builder._regime_context(None, None) == ""

    def test_vix_included_when_provided(self, builder):
        ctx = builder._regime_context("BULL_LOW_VIX", "13.5")
        assert "13.5" in ctx
