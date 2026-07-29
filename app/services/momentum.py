import math
from app.logger import get_logger
from config import (
    MOMENTUM_WEIGHT_1M, MOMENTUM_WEIGHT_3M, MOMENTUM_WEIGHT_6M, MOMENTUM_WEIGHT_VOL,
    MOMENTUM_50DMA_PENALTY, MOMENTUM_200DMA_PENALTY,
    MOMENTUM_VOL_BASELINE, MOMENTUM_VOL_QUALITY_MIN, MOMENTUM_VOL_QUALITY_MAX,
    MOMENTUM_VOL_CAP, MOMENTUM_VOL_BASELINE_DAYS,
    MOMENTUM_52W_NEAR_BONUS, MOMENTUM_52W_FAR_BONUS, MOMENTUM_52W_NEAR_PCT, MOMENTUM_52W_FAR_PCT,
    MOMENTUM_RSI_LOW, MOMENTUM_RSI_SWEET_LOW, MOMENTUM_RSI_SWEET_HIGH, MOMENTUM_RSI_HIGH,
    MOMENTUM_RSI_SWEET_BONUS, MOMENTUM_RSI_OVERBOUGHT_PENALTY, MOMENTUM_RSI_WEAK_PENALTY,
)

logger = get_logger(__name__)


class MomentumCalculator:

    def _calculate_rsi(self, closes, period=14):
        delta = closes.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        # Wilder's smoothing via EWM (com = period - 1)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(100)  # all-gain streaks → RSI 100
        return float(rsi.iloc[-1])

    def calculate_score(self, df):

        # Need 200 rows for 200 DMA
        if len(df) < 200:
            return None

        try:

            current = float(df["Close"].iloc[-1])

            # 20 DMA — hard filter: stock must have short-term momentum
            ma20  = float(df["Close"].rolling(20).mean().iloc[-1])
            if current < ma20:
                return None

            # 200 DMA — soft penalty for long-term downtrend (still shown, ranked lower)
            ma200 = float(df["Close"].rolling(200).mean().iloc[-1])
            below_200dma = current < ma200

            # Returns
            close_1m = float(df["Close"].iloc[-21])
            close_3m = float(df["Close"].iloc[-63])
            close_6m = float(df["Close"].iloc[-126])

            return_1m = ((current - close_1m) / close_1m) * 100
            return_3m = ((current - close_3m) / close_3m) * 100
            return_6m = ((current - close_6m) / close_6m) * 100

            # Volume score — 63-day rolling baseline vs recent 10-day average.
            # Using (ratio - 1) so normal volume = 0 contribution; above-normal = positive;
            # below-normal = negative. Cap at 2.5x to prevent single-spike distortion.
            baseline_vol = float(df["Volume"].tail(MOMENTUM_VOL_BASELINE_DAYS).mean())
            recent_vol   = float(df["Volume"].tail(10).mean())
            if baseline_vol == 0:
                volume_ratio = 0.0
            else:
                volume_ratio = min(recent_vol / baseline_vol, MOMENTUM_VOL_CAP)
            volume_score = (volume_ratio - 1.0) * 20

            # 50 DMA
            ma50 = float(df["Close"].rolling(50).mean().iloc[-1])

            # Base weighted score — recency premium on 1M
            score = (
                return_1m * MOMENTUM_WEIGHT_1M
                + return_3m * MOMENTUM_WEIGHT_3M
                + return_6m * MOMENTUM_WEIGHT_6M
                + volume_score * MOMENTUM_WEIGHT_VOL
            )

            # Penalise below 50 DMA (short-term weakness)
            if current < ma50:
                score -= MOMENTUM_50DMA_PENALTY

            if below_200dma:
                score -= MOMENTUM_200DMA_PENALTY

            # ── VOLATILITY ADJUSTMENT ──────────────────────────────
            # High-volatility stocks have inflated raw returns.
            # Scale score by quality factor: baseline = target annualized vol.
            daily_ret = df["Close"].pct_change().dropna()
            ann_vol = float(daily_ret.tail(63).std() * math.sqrt(252) * 100)
            # quality > 1 rewards low-vol stocks, < 1 penalizes high-vol
            vol_quality = max(
                MOMENTUM_VOL_QUALITY_MIN,
                min(MOMENTUM_VOL_QUALITY_MAX, MOMENTUM_VOL_BASELINE / max(ann_vol, 10.0))
            )
            score = score * vol_quality

            # ── 52-WEEK HIGH PROXIMITY ─────────────────────────────
            # Stocks near 52w highs continue higher — documented alpha signal.
            lookback = min(252, len(df))
            high_52w = float(df["High"].rolling(lookback).max().iloc[-1])
            proximity = (current / high_52w) * 100

            if proximity >= MOMENTUM_52W_NEAR_PCT:
                score += MOMENTUM_52W_NEAR_BONUS
            elif proximity >= MOMENTUM_52W_FAR_PCT:
                score += MOMENTUM_52W_FAR_BONUS

            # ── RSI ENTRY FILTER ───────────────────────────────────
            # Ideal entry: RSI 50-70 (trending, not overbought)
            rsi = self._calculate_rsi(df["Close"])

            if MOMENTUM_RSI_SWEET_LOW <= rsi <= MOMENTUM_RSI_SWEET_HIGH:
                score += MOMENTUM_RSI_SWEET_BONUS
            elif rsi > MOMENTUM_RSI_HIGH:
                score -= MOMENTUM_RSI_OVERBOUGHT_PENALTY
            elif rsi < MOMENTUM_RSI_LOW:
                score -= MOMENTUM_RSI_WEAK_PENALTY

            return round(score, 2)

        except Exception as e:
            logger.error("Momentum calculation error: %s", e)
            return None
