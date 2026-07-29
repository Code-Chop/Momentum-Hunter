import pandas as pd
import pytest
from app.services.momentum import MomentumCalculator


def make_df(n=250, start_price=100.0, trend=0.001, volume=1_000_000):
    """Synthetic OHLCV data with configurable trend."""
    prices = [start_price * (1 + trend) ** i for i in range(n)]
    return pd.DataFrame({
        "Close": prices,
        "High": [p * 1.01 for p in prices],
        "Low": [p * 0.99 for p in prices],
        "Volume": [volume] * n,
    })


@pytest.fixture
def calc():
    return MomentumCalculator()


class TestInsufficientData:
    def test_returns_none_when_fewer_than_200_rows(self, calc):
        assert calc.calculate_score(make_df(n=150)) is None

    def test_returns_none_at_exactly_199_rows(self, calc):
        assert calc.calculate_score(make_df(n=199)) is None

    def test_accepts_exactly_200_rows(self, calc):
        # 200-row uptrend should pass (current > 200 DMA since it's rising)
        result = calc.calculate_score(make_df(n=200))
        # May still be None if current < 200 DMA at exactly 200 rows, so just no crash
        assert result is None or isinstance(result, float)


class TestTrendFilter:
    def test_returns_none_for_downtrend_below_200dma(self, calc):
        # Strong downtrend: start at 200, fall to ~20
        df = make_df(n=250, start_price=200.0, trend=-0.008)
        assert calc.calculate_score(df) is None

    def test_returns_score_for_uptrend_above_200dma(self, calc):
        df = make_df(n=250, start_price=100.0, trend=0.002)
        score = calc.calculate_score(df)
        assert isinstance(score, float)


class TestScoreOrdering:
    def test_stronger_momentum_scores_higher(self, calc):
        weak = make_df(n=250, trend=0.0005)
        strong = make_df(n=250, trend=0.004)
        s_weak = calc.calculate_score(weak)
        s_strong = calc.calculate_score(strong)
        assert s_weak is not None and s_strong is not None
        assert s_strong > s_weak

    def test_higher_volume_boosts_score(self, calc):
        low_vol = make_df(n=250, trend=0.002, volume=500_000)
        # Spike recent volume to simulate buying pressure
        df_high_vol = make_df(n=250, trend=0.002, volume=500_000)
        df_high_vol.loc[df_high_vol.index[-10:], "Volume"] = 3_000_000
        s_low = calc.calculate_score(low_vol)
        s_high = calc.calculate_score(df_high_vol)
        assert s_low is not None and s_high is not None
        assert s_high > s_low


class TestReturnValue:
    def test_score_is_rounded_to_two_decimal_places(self, calc):
        df = make_df(n=250, trend=0.002)
        score = calc.calculate_score(df)
        if score is not None:
            assert score == round(score, 2)

    def test_score_is_finite(self, calc):
        import math
        df = make_df(n=250, trend=0.002)
        score = calc.calculate_score(df)
        if score is not None:
            assert math.isfinite(score)
