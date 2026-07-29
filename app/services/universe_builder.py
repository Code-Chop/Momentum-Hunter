"""
Universe builder.

Fetches NSE index constituent lists and filters for liquid, tradeable stocks.
Run once every few months to pick up index reconstitutions.

Sources:
  Nifty 500       - top 500 by market cap (large + mid + small)
  Nifty Microcap 250 - next 250 stocks below Nifty500 by market cap

Combined unique universe: ~755 symbols before liquidity filtering.

Filters:
  - Price       >= Rs 50
  - Avg volume  >= 500,000 shares/day
  - Avg value   >= Rs 5 crore/day
"""

import time
import pandas as pd
import yfinance as yf
from app.logger import get_logger

logger = get_logger(__name__)

_INDEX_URLS = {
    "Nifty500":    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "Microcap250": "https://archives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}

MIN_PRICE       = 50
MIN_AVG_VOLUME  = 500_000
MIN_DAILY_VALUE = 5_00_00_000   # Rs 5 crore/day


class UniverseBuilder:

    def build_nifty500(self):
        """Legacy entry point."""
        return self.build()

    def build(self):
        # ── Fetch and merge all index lists ───────────────────────────
        all_rows = []
        for index_name, url in _INDEX_URLS.items():
            try:
                df = pd.read_csv(url)
                df["_index"] = index_name
                all_rows.append(df)
                logger.info("%s: %d constituents", index_name, len(df))
                print(f"  {index_name}: {len(df)} stocks")
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", index_name, e)

        if not all_rows:
            raise RuntimeError("Could not fetch any index list from NSE")

        combined   = pd.concat(all_rows, ignore_index=True)
        combined   = combined.drop_duplicates(subset="Symbol", keep="first")
        sector_map = dict(zip(combined["Symbol"], combined["Industry"]))
        symbols    = combined["Symbol"].tolist()

        print(f"\nTotal unique symbols: {len(symbols)} - checking liquidity...\n")

        # ── Liquidity filter via yfinance ─────────────────────────────
        passed, skipped = [], 0

        for idx, symbol in enumerate(symbols, 1):
            try:
                ticker  = yf.Ticker(f"{symbol}.NS")
                df      = ticker.history(period="3mo")

                if len(df) < 20:
                    print(f"[{idx}/{len(symbols)}] {symbol:<20} -- not enough data")
                    skipped += 1
                    continue

                price   = float(df["Close"].iloc[-1])
                avg_vol = float(df["Volume"].mean())
                avg_val = float((df["Close"] * df["Volume"]).mean())

                if price < MIN_PRICE or avg_vol < MIN_AVG_VOLUME or avg_val < MIN_DAILY_VALUE:
                    print(f"[{idx}/{len(symbols)}] {symbol:<20} -- filtered  price={price:.0f}  vol={avg_vol/1e5:.1f}L  val={avg_val/1e7:.1f}Cr")
                    skipped += 1
                    continue

                passed.append({"symbol": symbol, "sector": sector_map.get(symbol, "Unknown")})
                print(f"[{idx}/{len(symbols)}] {symbol:<20} OK  price={price:.0f}  vol={avg_vol/1e5:.1f}L  val={avg_val/1e7:.1f}Cr")

            except Exception as e:
                print(f"[{idx}/{len(symbols)}] {symbol:<20} -- error: {e}")
                skipped += 1

            # gentle rate limiting
            if idx % 10 == 0:
                time.sleep(0.5)

        # ── Save ──────────────────────────────────────────────────────
        stocks = pd.DataFrame(passed)
        stocks.to_csv("app/data/stocks.csv", index=False)

        print(f"\n{'='*50}")
        print(f"Saved {len(stocks)} stocks  ({skipped} filtered out)")
        print(f"{'='*50}\n")
        print(stocks["sector"].value_counts().to_string())

        return stocks
