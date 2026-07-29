"""
Real-time NSE data via NSE India's unofficial public API.

Cookie strategy (in order of preference):
  1. Own session init (headers-based) — works sometimes
  2. Chrome cookie extraction via browser_cookie3 — reliable when Chrome has NSE open
  3. Auto-open NSE in browser → wait for Cloudflare solve → re-read cookies
  4. Fall back to yfinance (15-min delayed) if all above fail

Keep nseindia.com open in a Chrome tab while trading for best results.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
import requests
from app.logger import get_logger

logger = get_logger(__name__)

_BASE = "https://www.nseindia.com"

_INIT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language":           "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding":           "gzip, deflate, br",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "none",
    "Sec-Fetch-User":            "?1",
    "Cache-Control":             "max-age=0",
}

_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.nseindia.com/",
    "Sec-Fetch-Dest":  "empty",
    "Sec-Fetch-Mode":  "cors",
    "Sec-Fetch-Site":  "same-origin",
    "Connection":      "keep-alive",
}

_INIT_URLS = [
    _BASE,
    f"{_BASE}/market-data/live-equity-market",
    f"{_BASE}/get-quotes/equity",
]

_SESSION_TTL          = 270   # refresh own cookies every 4.5 min
_BROWSER_REFRESH_WAIT = 6     # seconds to wait after opening browser tab
_ALL_INDICES_URL      = f"{_BASE}/api/allIndices"
_NIFTY500_URL         = f"{_BASE}/api/equity-stockIndices?index=NIFTY%20500"

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


class NseLiveService:

    def __init__(self):
        self._session            = requests.Session()
        self._last_init          = 0.0
        self._last_browser_open  = 0.0   # rate-limit browser opens to once per 5 min
        self._browser_proc       = None  # Popen for the managed Chrome instance
        self._browser_temp_dir   = None  # temp --user-data-dir for that instance
        self._init_session()

    # ── Session management ────────────────────────────────────────────

    def _init_session(self) -> bool:
        """Own headers-based init — works when Cloudflare isn't blocking."""
        self._session.headers.update(_INIT_HEADERS)
        success = False
        for url in _INIT_URLS:
            try:
                r = self._session.get(url, timeout=10)
                if r.status_code < 500:
                    time.sleep(0.5)
                    success = True
                    break
            except Exception as e:
                logger.debug("NSE init attempt failed [%s]: %s", url, e)

        self._last_init = time.time()
        self._session.headers.update(_API_HEADERS)

        n = len(self._session.cookies)
        if n > 0:
            logger.debug("NSE session ready via own init (cookies: %d)", n)
            return True
        if not success:
            logger.debug("NSE own init failed — will try browser cookies")
        return False

    def _find_chrome(self) -> str | None:
        chrome = shutil.which("chrome") or shutil.which("google-chrome")
        if chrome:
            return chrome
        for p in _CHROME_PATHS:
            if os.path.exists(p):
                return p
        return None

    def _close_browser(self):
        """Kill the managed Chrome instance and clean up its temp profile."""
        if self._browser_proc is not None:
            try:
                if self._browser_proc.poll() is None:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self._browser_proc.pid)],
                            capture_output=True, timeout=5,
                        )
                    else:
                        self._browser_proc.terminate()
                        try:
                            self._browser_proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._browser_proc.kill()
            except Exception as e:
                logger.debug("Browser close error: %s", e)
            self._browser_proc = None

        if self._browser_temp_dir:
            shutil.rmtree(self._browser_temp_dir, ignore_errors=True)
            self._browser_temp_dir = None

    def _load_browser_cookies(self) -> bool:
        """
        Read NSE cookies from the managed Chrome profile (if open) or the
        user's default Chrome profile and inject into session.
        """
        try:
            import browser_cookie3
            kwargs = {"domain_name": "nseindia.com"}
            if self._browser_temp_dir:
                cookie_file = os.path.join(self._browser_temp_dir, "Default", "Cookies")
                key_file    = os.path.join(self._browser_temp_dir, "Local State")
                if os.path.exists(cookie_file):
                    kwargs["cookie_file"] = cookie_file
                if os.path.exists(key_file):
                    kwargs["key_file"] = key_file
            jar     = browser_cookie3.chrome(**kwargs)
            cookies = {c.name: c.value for c in jar}
            if cookies:
                self._session.cookies.update(cookies)
                self._last_init = time.time()
                logger.debug("Loaded %d NSE cookies from Chrome", len(cookies))
                return True
        except Exception as e:
            logger.debug("Chrome cookie read failed: %s", e)
        return False

    def _open_nse_in_browser(self):
        """
        Open NSE in a managed Chrome instance to trigger a fresh Cloudflare solve.
        Closes the previous managed window before opening a new one, so tabs
        never accumulate. Rate-limited to once every 5 minutes.
        """
        now = time.time()
        if now - self._last_browser_open < 300:
            logger.debug("Skipping browser open — opened %.0fs ago", now - self._last_browser_open)
            return

        self._close_browser()  # exit the old window before opening a new one

        self._last_browser_open = now
        url    = f"{_BASE}/market-data/live-equity-market"
        chrome = self._find_chrome()

        if chrome:
            self._browser_temp_dir = tempfile.mkdtemp(prefix="nse_chrome_")
            logger.info("Opening NSE in browser to refresh Cloudflare cookies (~%ds wait)...", _BROWSER_REFRESH_WAIT)
            self._browser_proc = subprocess.Popen(
                [
                    chrome,
                    f"--user-data-dir={self._browser_temp_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-default-apps",
                    url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            logger.info("Chrome not found — opening NSE in default browser (tabs may accumulate)")
            webbrowser.open(url)

        time.sleep(_BROWSER_REFRESH_WAIT)

    def _ensure_session(self):
        if time.time() - self._last_init > _SESSION_TTL:
            self._init_session()

    # ── Core GET with cookie fallback chain ───────────────────────────

    def _get(self, url: str) -> dict | None:
        """
        GET with a three-stage cookie recovery:
          1. Own session
          2. Chrome cookies (if NSE is open in browser)
          3. Open browser → wait → fresh Chrome cookies
        Falls back to None (yfinance handles it) if all stages fail.
        """
        self._ensure_session()

        for attempt in range(3):
            try:
                r = self._session.get(url, timeout=10)

                # Auth failure — rate-limited reinit (avoid spamming on bulk calls)
                if r.status_code in (401, 403):
                    if time.time() - self._last_init > 10:
                        self._init_session()
                    continue

                if not r.ok:
                    logger.debug("NSE %d for %s", r.status_code, url)
                    return None

                # Strip whitespace — empty body can be b"" or b"\n" or b"\r\n"
                body = (r.content or b"").strip()

                # Empty or HTML = Cloudflare bot-detection returning 200 OK
                if not body or body[:1] == b"<":
                    if attempt == 0:
                        logger.debug("NSE bot-detection — trying Chrome cookies")
                        self._load_browser_cookies()
                    elif attempt == 1:
                        logger.debug("Chrome cookies stale — opening browser for fresh solve")
                        self._open_nse_in_browser()
                        self._load_browser_cookies()
                    else:
                        logger.debug("All cookie strategies exhausted for %s", url)
                        return None
                    continue

                try:
                    return r.json()
                except ValueError:
                    # Body looked valid but isn't JSON — treat as bot-detection
                    logger.debug("NSE non-JSON body attempt %d for %s", attempt, url)
                    if attempt == 0:
                        self._load_browser_cookies()
                    elif attempt == 1:
                        self._open_nse_in_browser()
                        self._load_browser_cookies()
                    else:
                        return None
                    continue

            except Exception as e:
                logger.debug("NSE request error [%s]: %s", url, e)
                return None

        return None

    # ── All indices (single call) ─────────────────────────────────────

    def get_all_indices(self) -> dict:
        """
        Fetch ALL NSE indices in one API call.
        Returns {UPPERCASE_INDEX_NAME: {last, change_pct, open, high, low, prev_close}}
        """
        data = self._get(_ALL_INDICES_URL)
        if not data:
            return {}

        result = {}
        for row in data.get("data", []):
            name = (row.get("index") or "").upper()
            last = row.get("last") or row.get("lastPrice")
            if name and last:
                result[name] = {
                    "last":       float(last),
                    "change_pct": row.get("percentChange") or row.get("pChange") or 0,
                    "open":       row.get("open"),
                    "high":       row.get("high") or row.get("dayHigh"),
                    "low":        row.get("low")  or row.get("dayLow"),
                    "prev_close": row.get("previousClose") or row.get("prevClose"),
                    "year_high":  row.get("yearHigh"),
                    "year_low":   row.get("yearLow"),
                }
        logger.debug("allIndices: fetched %d indices", len(result))
        return result

    # ── Single index quote (fallback) ─────────────────────────────────

    def get_index(self, index_name: str) -> dict | None:
        url  = f"{_BASE}/api/equity-stockIndices?index={requests.utils.quote(index_name)}"
        data = self._get(url)
        if not data:
            return None

        items = data.get("data", [])
        if not items:
            return None

        row = items[0]
        return {
            "last":       row.get("last") or row.get("lastPrice") or row.get("indexValue"),
            "change_pct": row.get("percentChange") or row.get("pChange"),
            "open":       row.get("open"),
            "high":       row.get("high") or row.get("dayHigh"),
            "low":        row.get("low")  or row.get("dayLow"),
            "prev_close": row.get("previousClose") or row.get("prevClose"),
            "year_high":  row.get("yearHigh"),
            "year_low":   row.get("yearLow"),
        }

    # ── Individual stock quote ────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict | None:
        url  = f"{_BASE}/api/quote-equity?symbol={requests.utils.quote(symbol.upper())}"
        data = self._get(url)
        if not data:
            return None

        price = data.get("priceInfo", {})
        hl    = price.get("intraDayHighLow", {})

        return {
            "last":       price.get("lastPrice"),
            "change_pct": price.get("pChange"),
            "open":       price.get("open"),
            "high":       hl.get("max") or price.get("dayHigh"),
            "low":        hl.get("min") or price.get("dayLow"),
            "prev_close": price.get("previousClose"),
            "vwap":       price.get("vwap"),
            "volume":     data.get("marketDeptOrderBook", {})
                              .get("totalBuyQuantity"),
        }

    # ── Bulk stock quotes (preferred) ─────────────────────────────────

    def get_quotes_bulk(self, symbols: list[str], delay: float = 0.3) -> dict:
        """
        Fetch prices for multiple symbols via NIFTY 500 index (one call).
        Falls back to individual quote calls for any not in NIFTY 500.
        """
        results = {}
        missing = list(symbols)

        bulk = self._get(_NIFTY500_URL)
        if bulk:
            symbol_set = {s.upper() for s in symbols}
            for row in bulk.get("data", []):
                sym  = (row.get("symbol") or "").upper()
                last = row.get("lastPrice") or row.get("last")
                if sym in symbol_set and last:
                    results[sym] = {
                        "last":       float(last),
                        "change_pct": row.get("pChange") or row.get("percentChange"),
                        "open":       row.get("open"),
                        "high":       row.get("dayHigh") or row.get("high"),
                        "low":        row.get("dayLow")  or row.get("low"),
                        "prev_close": row.get("previousClose") or row.get("prevClose"),
                    }
            missing = [s for s in symbols if s.upper() not in results]
            logger.debug("Bulk NSE fetch: %d/%d found", len(results), len(symbols))

        for sym in missing:
            q = self.get_quote(sym)
            if q and q.get("last"):
                results[sym.upper()] = q
            time.sleep(delay)

        return results
