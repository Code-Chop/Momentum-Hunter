"""
Angel One SmartAPI client.

Provides real-time NSE quotes and intraday OHLCV candles as a faster
replacement for yfinance during market hours.

Flow:
  1. Login once per session using API key + TOTP
  2. Cache the access token (valid ~24h)
  3. For intraday scans: fetch all symbols via marketData (single bulk call)
  4. For candle data: fetch per symbol via getCandleData
  5. Falls back silently — caller always gets None on any failure

Requires:
  pip install smartapi-python pyotp
"""
import json
import time
import pickle
import requests
from datetime import datetime, date, timedelta
from pathlib import Path

from app.logger import get_logger
from config import ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET

logger = get_logger(__name__)

_SESSION_FILE    = Path("app/data/.angel_session.pkl")
_TOKENS_FILE     = Path("app/data/.angel_tokens.pkl")
_TOKENS_URL      = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
_TOKENS_MAX_AGE  = 86400   # refresh instruments file once a day


class AngelOneService:

    def __init__(self):
        self._api          = None
        self._access_token = None
        self._session_date = None
        self._tokens: dict = {}   # "RELIANCE" → "2885"
        self._ready        = False

        if not all([ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET]):
            logger.debug("Angel One credentials not configured — service disabled")
            return

        self._ready = self._connect()

    # ── Auth ──────────────────────────────────────────────────────────

    def _connect(self) -> bool:
        """Login and cache the session. Returns True on success."""
        try:
            import pyotp
            from SmartApi import SmartConnect

            # Reuse today's cached session if available
            cached = self._load_session()
            if cached:
                api = SmartConnect(api_key=ANGEL_API_KEY)
                api.setAccessToken(cached["access_token"])
                api.setRefreshToken(cached["refresh_token"])
                if cached.get("user_id"):
                    api.setUserId(cached["user_id"])
                self._api          = api
                self._access_token = cached["access_token"]
                logger.debug("Angel One: reused cached session")
                return True

            totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
            api  = SmartConnect(api_key=ANGEL_API_KEY)
            data = api.generateSession(ANGEL_CLIENT_ID, ANGEL_PASSWORD, totp)

            if data.get("status") is False:
                logger.warning("Angel One login failed: %s", data.get("message"))
                return False

            # api.access_token is the raw JWT (set by setAccessToken inside generateSession)
            # data["data"]["jwtToken"] already has "Bearer " prefix — don't use that for storage
            raw_token     = api.access_token
            refresh_token = data["data"]["refreshToken"]

            self._api          = api
            self._access_token = raw_token
            self._save_session({
                "access_token":  raw_token,
                "refresh_token": refresh_token,
                "user_id":       api.userId or "",
            })
            logger.info("Angel One: logged in successfully")
            return True

        except ImportError:
            logger.warning("SmartApi or pyotp not installed — run: pip install smartapi-python websocket-client logzero pyotp")
            return False
        except Exception as e:
            logger.warning("Angel One connect failed: %s", e)
            return False

    def _load_session(self) -> dict | None:
        if not _SESSION_FILE.exists():
            return None
        try:
            data = pickle.loads(_SESSION_FILE.read_bytes())
            if data.get("date") == str(date.today()):
                return data
        except Exception:
            pass
        return None

    def _save_session(self, tokens: dict):
        try:
            _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SESSION_FILE.write_bytes(pickle.dumps({**tokens, "date": str(date.today())}))
        except Exception:
            pass

    # ── Symbol → Token map ────────────────────────────────────────────

    def _ensure_tokens(self):
        """Load NSE equity token map from cache or download fresh."""
        if self._tokens:
            return

        # Try cache
        if _TOKENS_FILE.exists():
            age = time.time() - _TOKENS_FILE.stat().st_mtime
            if age < _TOKENS_MAX_AGE:
                try:
                    self._tokens = pickle.loads(_TOKENS_FILE.read_bytes())
                    logger.debug("Angel One: loaded %d symbol tokens from cache", len(self._tokens))
                    return
                except Exception:
                    pass

        # Download fresh
        try:
            logger.info("Angel One: downloading instruments file...")
            resp = requests.get(_TOKENS_URL, timeout=30)
            instruments = resp.json()
            mapping = {}
            for item in instruments:
                if item.get("exch_seg") != "NSE":
                    continue
                sym = item.get("symbol", "")
                # Strip exchange suffix: "RELIANCE-EQ" → "RELIANCE"
                clean = sym.split("-")[0].split("_")[0].strip()
                if clean and item.get("token"):
                    mapping[clean] = item["token"]
            self._tokens = mapping
            _TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
            _TOKENS_FILE.write_bytes(pickle.dumps(mapping))
            logger.info("Angel One: cached %d symbol tokens", len(mapping))
        except Exception as e:
            logger.warning("Angel One: instruments download failed: %s", e)

    def _get_token(self, symbol: str) -> str | None:
        self._ensure_tokens()
        # Try exact match first (index names like "India VIX", "Nifty IT" are mixed-case)
        return self._tokens.get(symbol) or self._tokens.get(symbol.upper())

    # ── Public API ────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._ready and self._api is not None

    def get_ltp_bulk(self, symbols: list[str]) -> dict:
        """
        Fetch last traded prices for multiple symbols in a single API call.
        Returns {SYMBOL: price}. Missing symbols are silently skipped.
        """
        if not self.is_ready:
            return {}

        self._ensure_tokens()
        token_to_sym = {}
        tokens = []

        for sym in symbols:
            tok = self._get_token(sym)
            if tok:
                tokens.append(tok)
                token_to_sym[tok] = sym  # preserve original casing (e.g. "India VIX")

        if not tokens:
            return {}

        try:
            resp = self._api.getMarketData("LTP", {"NSE": tokens})

            if not resp or resp.get("status") is False:
                logger.warning("Angel One getMarketData failed: %s", resp.get("message") if resp else "no response")
                return {}

            result = {}
            for item in resp.get("data", {}).get("fetched", []):
                tok = str(item.get("symbolToken", ""))
                ltp = item.get("ltp")
                if tok in token_to_sym and ltp is not None:
                    result[token_to_sym[tok]] = round(float(ltp), 2)

            logger.debug("Angel One bulk LTP: %d/%d symbols fetched", len(result), len(symbols))
            return result

        except Exception as e:
            logger.warning("Angel One get_ltp_bulk failed: %s", e)
            return {}

    def get_candles(self, symbol: str, interval: str = "FIFTEEN_MINUTE", days: int = 5):
        """
        Fetch OHLCV candle data. Returns a pandas DataFrame with the same
        column structure as yfinance (Open, High, Low, Close, Volume) so it
        drops in as a replacement.

        interval options: ONE_MINUTE, THREE_MINUTE, FIVE_MINUTE, TEN_MINUTE,
                          FIFTEEN_MINUTE, THIRTY_MINUTE, ONE_HOUR, ONE_DAY
        """
        if not self.is_ready:
            return None

        token = self._get_token(symbol)
        if not token:
            logger.debug("Angel One: no token for %s", symbol)
            return None

        try:
            import pandas as pd

            now      = datetime.now()
            from_dt  = now - timedelta(days=days)
            params   = {
                "exchange":    "NSE",
                "symboltoken": token,
                "interval":    interval,
                "fromdate":    from_dt.strftime("%Y-%m-%d %H:%M"),
                "todate":      now.strftime("%Y-%m-%d %H:%M"),
            }
            resp = self._api.getCandleData(params)

            if not resp or resp.get("status") is False:
                logger.debug("Angel One candles failed for %s: %s", symbol, resp.get("message") if resp else "no response")
                return None

            candles = resp.get("data", [])
            if not candles:
                return None

            df = pd.DataFrame(candles, columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            df = df.set_index("Datetime").sort_index()
            df = df.astype(float)

            logger.debug("Angel One candles for %s: %d bars", symbol, len(df))
            return df

        except Exception as e:
            logger.warning("Angel One get_candles failed for %s: %s", symbol, e)
            return None


# Module-level singleton — one login for the entire process lifetime
_instance: AngelOneService | None = None

def get_angel_one() -> AngelOneService:
    global _instance
    if _instance is None:
        _instance = AngelOneService()
    return _instance
