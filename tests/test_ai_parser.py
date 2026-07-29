import json
import pytest
from app.services.ai_parser import AIParser


def make_response(**kwargs):
    base = {
        "stocks": [{"symbol": "RELIANCE", "conviction": 8.5}],
        "highest_conviction": "RELIANCE",
        "avoid": "COAL",
        "market_sentiment": "Bullish",
    }
    base.update(kwargs)
    return json.dumps(base)


@pytest.fixture
def parser():
    return AIParser()


class TestValidInput:
    def test_parses_valid_json(self, parser):
        result = parser.parse(make_response())
        assert result is not None
        assert result["stocks"][0]["symbol"] == "RELIANCE"
        assert result["market_sentiment"] == "Bullish"

    def test_strips_markdown_json_fence(self, parser):
        wrapped = f"```json\n{make_response()}\n```"
        assert parser.parse(wrapped) is not None

    def test_strips_plain_markdown_fence(self, parser):
        wrapped = f"```\n{make_response()}\n```"
        assert parser.parse(wrapped) is not None

    def test_handles_optional_highest_risk(self, parser):
        result = parser.parse(make_response(highest_risk="ADANI"))
        assert result is not None  # highest_risk is optional — should not fail


class TestEmptyOrMissingInput:
    def test_returns_none_for_empty_string(self, parser):
        assert parser.parse("") is None

    def test_returns_none_for_none(self, parser):
        assert parser.parse(None) is None

    def test_returns_none_for_invalid_json(self, parser):
        assert parser.parse("{not: valid}") is None

    def test_returns_none_for_missing_required_key(self, parser):
        incomplete = json.dumps({
            "stocks": [{"symbol": "X", "conviction": 7}],
            "highest_conviction": "X",
            # missing: avoid, market_sentiment
        })
        assert parser.parse(incomplete) is None

    def test_returns_none_for_empty_stocks_list(self, parser):
        r = make_response(stocks=[])
        assert parser.parse(r) is None


class TestConvictionClamping:
    def test_clamps_conviction_above_10(self, parser):
        r = make_response(stocks=[{"symbol": "X", "conviction": 15}])
        result = parser.parse(r)
        assert result["stocks"][0]["conviction"] == 10.0

    def test_clamps_conviction_below_1(self, parser):
        r = make_response(stocks=[{"symbol": "X", "conviction": -3}])
        result = parser.parse(r)
        assert result["stocks"][0]["conviction"] == 1.0

    def test_leaves_valid_conviction_unchanged(self, parser):
        r = make_response(stocks=[{"symbol": "X", "conviction": 7.5}])
        result = parser.parse(r)
        assert result["stocks"][0]["conviction"] == 7.5


class TestMalformedStockEntries:
    def test_skips_entry_missing_symbol(self, parser):
        r = make_response(stocks=[
            {"conviction": 7},
            {"symbol": "GOOD", "conviction": 8},
        ])
        result = parser.parse(r)
        assert len(result["stocks"]) == 1
        assert result["stocks"][0]["symbol"] == "GOOD"

    def test_skips_entry_with_non_numeric_conviction(self, parser):
        r = make_response(stocks=[
            {"symbol": "BAD", "conviction": "high"},
            {"symbol": "OK", "conviction": 6},
        ])
        result = parser.parse(r)
        assert len(result["stocks"]) == 1

    def test_returns_none_when_all_entries_malformed(self, parser):
        r = make_response(stocks=[{"conviction": 7}, {"no_symbol": True}])
        assert parser.parse(r) is None
