from app.logger import get_logger
from config import (
    INTRADAY_W_VOL,   INTRADAY_W_RET,   INTRADAY_W_RET5,
    INTRADAY_W_RS,    INTRADAY_W_VWAP,  INTRADAY_W_BREAK,
    INTRADAY_W_VOL_BEAR,  INTRADAY_W_RET_BEAR,  INTRADAY_W_RET5_BEAR,
    INTRADAY_W_RS_BEAR,   INTRADAY_W_VWAP_BEAR, INTRADAY_W_BREAK_BEAR,
    INTRADAY_RET_CAP, INTRADAY_RET5_CAP, INTRADAY_RS_CAP, INTRADAY_VOL_NORM,
)

logger = get_logger(__name__)


class IntradayScanner:

    def _calculate_vwap(self, df):
        try:
            today_start = df.index[-1].normalize()
            today_bars  = df[df.index >= today_start]
            if today_bars.empty:
                return None
            total_volume = today_bars["Volume"].sum()
            if total_volume == 0:
                return None
            typical = (today_bars["High"] + today_bars["Low"] + today_bars["Close"]) / 3
            return float((typical * today_bars["Volume"]).sum() / total_volume)
        except Exception:
            return None

    def calculate_score(self, df, nifty_return=None, regime=None):
        """
        Normalized 0-100 composite score.

        Each signal is scaled to [-1, 1] then blended with regime-aware weights.
        50 = neutral; >60 = decent setup; >75 = strong setup.

        Weights (normal / bear):
          Volume     0.20 / 0.15  — confirms the move
          Return 1   0.30 / 0.10  — last-bar momentum (bear: deweighted, avoid chasing)
          Return 5   0.20 / 0.10  — 25-min momentum
          RS alpha   0.15 / 0.45  — outperformance vs Nifty today (bear: primary signal)
          VWAP       0.10 / 0.10  — intraday trend filter
          Breakout   0.05 / 0.10  — prior-session range break
        """
        try:
            if df is None or len(df) < 25:
                return None

            bear = regime == "BEAR"

            current_close  = float(df["Close"].iloc[-1])
            previous_close = float(df["Close"].iloc[-2])
            current_volume = float(df["Volume"].iloc[-1])

            avg_volume = float(df["Volume"].tail(20).mean())
            if avg_volume == 0:
                return None

            volume_ratio = current_volume / avg_volume

            # Split today vs prior session
            today_start = df.index[-1].normalize()
            today_bars  = df[df.index >= today_start]
            prior_bars  = df[df.index <  today_start]

            # Breakout: close above prior session's highest high
            if not prior_bars.empty:
                prior_high = float(prior_bars["High"].max())
            else:
                prior_high = float(df["High"].iloc[:-1].max())
            breakout = current_close >= prior_high

            # Last-bar return (5-min momentum)
            return_pct = ((current_close - previous_close) / previous_close) * 100

            # 5-bar return (~25-min momentum)
            return_5 = (
                (current_close - float(df["Close"].iloc[-6]))
                / float(df["Close"].iloc[-6])
            ) * 100

            # VWAP
            vwap       = self._calculate_vwap(df)
            above_vwap = vwap is not None and current_close >= vwap

            # RS alpha: stock's cumulative intraday return minus Nifty's
            # Both measured from today's open for consistent time window.
            rs_vs_nifty = None
            intraday_return = return_pct  # fallback

            if len(today_bars) >= 1:
                # Prefer Open column (first bar's open = market open)
                first_bar = today_bars.iloc[0]
                open_price = float(
                    first_bar["Open"] if "Open" in df.columns else first_bar["Close"]
                )
                if open_price > 0:
                    intraday_return = ((current_close - open_price) / open_price) * 100

            if nifty_return and nifty_return != 0:
                rs_vs_nifty = round(intraday_return - nifty_return, 2)

            # ── Normalize each signal to [-1, 1] ──────────────────────
            # Volume: 0 = no volume, 1 = 2x+ average (strong confirmation)
            vol_factor = min(volume_ratio / INTRADAY_VOL_NORM, 1.0)

            # Returns: capped at configured %
            ret_factor  = max(-1.0, min(return_pct / INTRADAY_RET_CAP,  1.0))
            ret5_factor = max(-1.0, min(return_5   / INTRADAY_RET5_CAP, 1.0))

            # RS alpha: positive = outperforming Nifty today
            rs_factor = (
                max(-1.0, min(rs_vs_nifty / INTRADAY_RS_CAP, 1.0))
                if rs_vs_nifty is not None else 0.0
            )

            # VWAP: +1 above, -1 below, 0 if unavailable (no volume)
            vwap_factor = (
                1.0  if above_vwap
                else (-1.0 if vwap is not None else 0.0)
            )

            # Breakout: pure bonus [0, 1]
            break_factor = 1.0 if breakout else 0.0

            # ── Weighted blend ─────────────────────────────────────────
            if bear:
                raw = (
                    vol_factor   * INTRADAY_W_VOL_BEAR
                    + ret_factor   * INTRADAY_W_RET_BEAR
                    + ret5_factor  * INTRADAY_W_RET5_BEAR
                    + rs_factor    * INTRADAY_W_RS_BEAR
                    + vwap_factor  * INTRADAY_W_VWAP_BEAR
                    + break_factor * INTRADAY_W_BREAK_BEAR
                )
            else:
                raw = (
                    vol_factor   * INTRADAY_W_VOL
                    + ret_factor   * INTRADAY_W_RET
                    + ret5_factor  * INTRADAY_W_RET5
                    + rs_factor    * INTRADAY_W_RS
                    + vwap_factor  * INTRADAY_W_VWAP
                    + break_factor * INTRADAY_W_BREAK
                )

            # Scale [-1, 1] → [0, 100]
            score = round((raw + 1.0) * 50.0, 2)

            return {
                "score":        score,
                "volume_ratio": round(volume_ratio, 2),
                "return_pct":   round(return_pct, 2),
                "breakout":     breakout,
                "above_vwap":   above_vwap,
                "vwap":         round(vwap, 2) if vwap else None,
                "rs_vs_nifty":  rs_vs_nifty,
            }

        except Exception as e:
            logger.error("Scanner error: %s", e)
            return None
