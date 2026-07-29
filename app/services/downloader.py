import time
import pickle
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf
from app.logger import get_logger
from config import DOWNLOAD_MAX_RETRIES, DOWNLOAD_RETRY_DELAY

logger = get_logger(__name__)

_IST = timedelta(hours=5, minutes=30)

def _is_market_hours() -> bool:
    from datetime import time as dtime
    now_ist = (datetime.now(timezone.utc) + _IST).time()
    return dtime(9, 15) <= now_ist <= dtime(15, 30)

_CACHE_DIR = Path("app/data/.cache")


class StockDownloader:

    # ── Cache helpers ──────────────────────────────────────────────────

    def _cache_path(self, key: str) -> Path:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return _CACHE_DIR / f"{key}_{date.today()}.pkl"

    def _load_cache(self, key: str):
        path = self._cache_path(key)
        if path.exists():
            try:
                return pickle.loads(path.read_bytes())
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, df) -> None:
        try:
            self._cache_path(key).write_bytes(pickle.dumps(df))
        except Exception as e:
            logger.warning("Cache write failed for %s: %s", key, e)

    # ── Retry helper ───────────────────────────────────────────────────

    def _fetch_with_retry(self, fetch_fn, label, cache_key=None):
        """
        Call fetch_fn(), returning cached data if available today.
        Retries up to DOWNLOAD_MAX_RETRIES times on failure or empty result.
        """
        import pandas as pd

        if cache_key:
            cached = self._load_cache(cache_key)
            if cached is not None and not cached.empty:
                logger.debug("Cache hit: %s", cache_key)
                return cached

        last_exc = None
        last_data = pd.DataFrame()
        for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
            try:
                data = fetch_fn()
                if not data.empty:
                    if cache_key:
                        self._save_cache(cache_key, data)
                    return data
                last_data = data
                logger.warning("%s: empty data on attempt %d/%d, retrying...", label, attempt, DOWNLOAD_MAX_RETRIES)
            except Exception as e:
                last_exc = e
                logger.warning("%s: attempt %d/%d failed: %s", label, attempt, DOWNLOAD_MAX_RETRIES, e)
            if attempt < DOWNLOAD_MAX_RETRIES:
                time.sleep(DOWNLOAD_RETRY_DELAY * attempt)

        if last_exc:
            raise last_exc
        return last_data

    # ── Public API ─────────────────────────────────────────────────────

    def get_stock_data(self, symbol, period="1y"):
        ticker = yf.Ticker(f"{symbol}.NS")
        return self._fetch_with_retry(
            lambda: ticker.history(period=period),
            label=symbol,
            cache_key=f"{symbol}_{period}",
        )

    def get_index_data(self, symbol, period="5y"):
        ticker = yf.Ticker(symbol)
        return self._fetch_with_retry(
            lambda: ticker.history(period=period),
            label=symbol,
            cache_key=f"{symbol}_{period}",
        )

    def get_index_intraday_data(self, symbol):
        # For NIFTY50 specifically, try Angel One during market hours
        if _is_market_hours() and symbol == "^NSEI":
            try:
                from app.services.angel_one import get_angel_one
                ao = get_angel_one()
                if ao.is_ready:
                    df = ao.get_candles("NIFTY", interval="FIFTEEN_MINUTE", days=5)
                    if df is not None and not df.empty:
                        return df
            except Exception as e:
                logger.debug("Angel One index fetch failed, falling back: %s", e)

        def fetch():
            df = yf.download(symbol, interval="15m", period="5d", progress=False, auto_adjust=True)
            if not df.empty and hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)
            return df

        # Intraday data changes during the day — cache with hour granularity
        hour_key = f"{symbol}_intraday_{datetime.now().strftime('%Y%m%d_%H')}"
        return self._fetch_with_retry(fetch, label=symbol, cache_key=hour_key)

    def get_intraday_data(self, symbol):
        # During market hours try Angel One (real-time, fast) first
        if _is_market_hours():
            try:
                from app.services.angel_one import get_angel_one
                ao = get_angel_one()
                if ao.is_ready:
                    df = ao.get_candles(symbol, interval="FIFTEEN_MINUTE", days=5)
                    if df is not None and not df.empty:
                        logger.debug("Angel One candles for %s: %d bars", symbol, len(df))
                        return df
            except Exception as e:
                logger.debug("Angel One get_intraday_data failed for %s, falling back: %s", symbol, e)

        # Fallback: yfinance (used outside market hours or when Angel One unavailable)
        def fetch():
            df = yf.download(f"{symbol}.NS", interval="15m", period="5d", progress=False, auto_adjust=True)
            if not df.empty and hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)
            return df

        hour_key = f"{symbol}_NS_intraday_{datetime.now().strftime('%Y%m%d_%H')}"
        return self._fetch_with_retry(fetch, label=symbol, cache_key=hour_key)
