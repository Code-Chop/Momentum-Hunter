"""
Live market intelligence service.

Price/change data  → Angel One LTP (market hours) → yfinance fallback
DMA levels         → yfinance daily history (not time-sensitive)
"""
from datetime import datetime
import yfinance as yf
from app.logger import get_logger
from config import (
    INDEX_NIFTY, INDEX_BANKNIFTY, INDEX_VIX,
    INDEX_IT, INDEX_AUTO, INDEX_PHARMA,
)

logger = get_logger(__name__)

# Maps display name → (Angel One symbol, yfinance symbol)
_INDICES = {
    "NIFTY50":    ("NIFTY",         INDEX_NIFTY),
    "BANKNIFTY":  ("BANKNIFTY",     INDEX_BANKNIFTY),
    "VIX":        ("India VIX",     INDEX_VIX),
    "NIFTY_IT":   ("Nifty IT",      INDEX_IT),
    "NIFTY_AUTO": ("Nifty Auto",    INDEX_AUTO),
    "NIFTY_PHM":  ("Nifty Pharma",  INDEX_PHARMA),
}


class MarketIntelligence:

    def __init__(self):
        pass

    # ── Index snapshot ────────────────────────────────────────────────

    def get_index_snapshot(self) -> dict:
        """
        Return real-time data for all key indices.
        Tries Angel One LTP (market hours) first, falls back to yfinance.
        {name: {current, change_pct, above_ma50, above_ma200, ma50, ma200}}
        """
        # Bulk LTP from Angel One for all supported indices at once
        ao_symbols = [s for s, _ in _INDICES.values() if s is not None]
        ao_prices  = {}
        try:
            from app.services.angel_one import get_angel_one
            ao = get_angel_one()
            if ao.is_ready:
                ao_prices = ao.get_ltp_bulk(ao_symbols)
        except Exception as e:
            logger.debug("Angel One index LTP failed: %s", e)

        snapshot = {}
        for display_name, (ao_sym, yf_symbol) in _INDICES.items():
            try:
                entry = self._build_index_entry(display_name, ao_sym, yf_symbol, ao_prices)
                if entry:
                    snapshot[display_name] = entry
            except Exception as e:
                logger.warning("Snapshot failed for %s: %s", display_name, e)
        return snapshot

    def _build_index_entry(self, display_name: str, ao_sym: str | None, yf_symbol: str, ao_prices: dict) -> dict | None:
        # ── Live price: Angel One first, yfinance fallback ────────────
        ltp = ao_prices.get(ao_sym) if ao_sym else None

        if ltp is not None:
            # Angel One gives LTP but not % change — compute from yfinance prev close
            current    = float(ltp)
            change_pct = self._compute_change_pct(current, yf_symbol)
        else:
            logger.debug("Angel One unavailable for %s, falling back to yfinance", display_name)
            current, change_pct = self._yf_current(yf_symbol)
            if current is None:
                return None

        result = {"current": round(current, 2), "change_pct": change_pct}

        # VIX: trend direction only, no DMA needed
        if display_name == "VIX":
            result["trend"] = "rising" if change_pct > 0 else "falling"
            return result

        # ── DMA levels from yfinance daily history ────────────────────
        dma = self._yf_dma(yf_symbol)
        result.update(dma)
        if dma.get("ma50"):
            result["above_ma50"] = current > dma["ma50"]
        if dma.get("ma200"):
            result["above_ma200"] = current > dma["ma200"]

        return result

    def _compute_change_pct(self, current: float, yf_symbol: str) -> float:
        """Compute % change vs previous session close using yfinance daily data."""
        try:
            hist = yf.Ticker(yf_symbol).history(period="5d")
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                return round(((current - prev_close) / prev_close) * 100, 2)
        except Exception:
            pass
        return 0.0

    def _yf_current(self, symbol: str) -> tuple[float | None, float]:
        try:
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(period="5d", interval="15m")
            if hist.empty:
                return None, 0.0
            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            current = float(hist["Close"].iloc[-1])
            today   = hist.index[-1].normalize()
            prior   = hist[hist.index.normalize() < today]
            prev    = float(prior["Close"].iloc[-1]) if not prior.empty else current
            chg     = round(((current - prev) / prev) * 100, 2)
            return current, chg
        except Exception as e:
            logger.warning("yfinance current failed for %s: %s", symbol, e)
            return None, 0.0

    def _yf_dma(self, symbol: str) -> dict:
        try:
            ticker = yf.Ticker(symbol)
            daily  = ticker.history(period="1y")
            result = {}
            if len(daily) >= 50:
                result["ma50"]  = round(float(daily["Close"].rolling(50).mean().iloc[-1]), 2)
            if len(daily) >= 200:
                result["ma200"] = round(float(daily["Close"].rolling(200).mean().iloc[-1]), 2)
            return result
        except Exception as e:
            logger.warning("yfinance DMA failed for %s: %s", symbol, e)
            return {}

    # ── ATR for volatility-adjusted stops ────────────────────────────

    def get_stock_atr(self, symbol: str, period: int = 14) -> float | None:
        """
        ATR(14) from daily OHLC using Wilder's method.
        Used to set stops/targets that scale with actual stock volatility.
        """
        try:
            import pandas as pd
            df = yf.Ticker(f"{symbol}.NS").history(period="1mo")
            if len(df) < period + 1:
                return None
            tr = pd.concat([
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift(1)).abs(),
                (df["Low"]  - df["Close"].shift(1)).abs(),
            ], axis=1).max(axis=1)
            return float(tr.rolling(period).mean().iloc[-1])
        except Exception as e:
            logger.debug("ATR fetch failed for %s: %s", symbol, e)
            return None

    # ── Stock prices for picks ────────────────────────────────────────

    def get_stock_prices(self, symbols: list[str]) -> dict:
        """
        Return {symbol: current_price} using Angel One bulk LTP.
        Falls back to yfinance for any symbol Angel One misses.
        """
        prices = {}
        try:
            from app.services.angel_one import get_angel_one
            ao = get_angel_one()
            if ao.is_ready:
                prices = ao.get_ltp_bulk(symbols)
        except Exception as e:
            logger.debug("Angel One stock prices failed: %s", e)

        # yfinance fallback for any missing symbols
        missing = [s for s in symbols if s not in prices]
        for sym in missing:
            try:
                hist = yf.Ticker(f"{sym}.NS").history(period="2d", interval="15m")
                if not hist.empty:
                    prices[sym] = round(float(hist["Close"].iloc[-1]), 2)
            except Exception:
                pass

        return prices

    # ── Formatted text for Gemini prompts ────────────────────────────

    def format_for_prompt(self, snapshot: dict) -> str:
        now   = datetime.now().strftime("%d %b %Y %H:%M IST")
        lines = [f"Live Market Data — {now}", ""]

        for name, data in snapshot.items():
            if not data:
                continue
            chg = f"{data['change_pct']:+.2f}%" if data.get("change_pct") is not None else "N/A"

            if name == "VIX":
                lines.append(f"India VIX : {data['current']} ({chg}) — {data.get('trend', '')}")
                continue

            ma_tag = ""
            if "above_ma200" in data:
                ma_tag = " | above 200DMA ✅" if data["above_ma200"] else " | BELOW 200DMA ⚠"
            if "above_ma50" in data:
                ma_tag += " | above 50DMA" if data["above_ma50"] else " | below 50DMA"

            lines.append(f"{name:<12}: {data['current']:>10,.2f} ({chg}){ma_tag}")

        return "\n".join(lines)

    # ── Quick message for /check ──────────────────────────────────────

    def format_check_message(self, snapshot: dict) -> str:
        now   = datetime.now().strftime("%d %b %H:%M")
        lines = [f"📡 Live Market Pulse — {now}", ""]

        for name, data in snapshot.items():
            if not data:
                continue
            chg   = data.get("change_pct", 0) or 0
            arrow = "📈" if chg > 0 else ("📉" if chg < 0 else "➡️")

            if name == "VIX":
                icon = "🟢" if data["current"] < 15 else (
                       "🟡" if data["current"] < 20 else (
                       "🟠" if data["current"] < 25 else "🔴"))
                lines.append(
                    f"{icon} India VIX : {data['current']} ({chg:+.2f}%) "
                    f"{'↓ easing' if data.get('trend') == 'falling' else '↑ rising'}"
                )
                continue

            ma_tag = ""
            if "above_ma200" in data:
                ma_tag = " ✅" if data["above_ma200"] else " ⚠️ below 200DMA"

            lines.append(
                f"{arrow} {name:<12}: {data['current']:>10,.0f} ({chg:+.2f}%){ma_tag}"
            )

        return "\n".join(lines)
