"""
Run this script the morning after main.py to record what yesterday's picks
actually returned. Reads performance_log.csv, downloads closing prices for
each pick, and appends results to app/data/realized_returns.csv.

Usage:
    python track_returns.py
"""
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

PERF_LOG = "app/data/performance_log.csv"
RETURNS_FILE = "app/data/realized_returns.csv"


def get_trading_closes(symbol: str, from_date: str) -> dict:
    """
    Return a {date_str: close_price} map for the two trading days
    starting from from_date. Uses a 7-day window to handle weekends/holidays.
    """
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = start + timedelta(days=7)
    ticker = yf.Ticker(f"{symbol}.NS")
    df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    if df.empty:
        return {}
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    return {str(d.date()): float(c) for d, c in zip(df.index, df["Close"])}


def main():
    if not Path(PERF_LOG).exists():
        print(f"No performance log found at {PERF_LOG}. Run main.py first.")
        return

    perf_df = pd.read_csv(PERF_LOG)

    # Load already-tracked dates to avoid reprocessing
    already_tracked = set()
    if Path(RETURNS_FILE).exists():
        existing = pd.read_csv(RETURNS_FILE)
        already_tracked = set(zip(existing["pick_date"], existing["symbol"]))

    # Find the most recent date with picks that hasn't been tracked yet
    all_dates = sorted(perf_df["date"].unique(), reverse=True)
    target_dates = [d for d in all_dates if any(
        (d, sym) not in already_tracked
        for sym in perf_df[perf_df["date"] == d]["symbol"]
    )]

    if not target_dates:
        print("All picks are already tracked. Nothing to do.")
        return

    rows = []
    for pick_date in target_dates:
        picks = perf_df[perf_df["date"] == pick_date]
        print(f"\nTracking {len(picks)} picks from {pick_date}...")

        for _, row in picks.iterrows():
            symbol = row["symbol"]
            if (pick_date, symbol) in already_tracked:
                continue

            try:
                closes = get_trading_closes(symbol, pick_date)
                sorted_dates = sorted(closes.keys())

                if len(sorted_dates) < 2:
                    print(f"  {symbol}: not enough price data yet — try again tomorrow")
                    continue

                entry_date = sorted_dates[0]
                exit_date = sorted_dates[1]
                entry_price = closes[entry_date]
                exit_price = closes[exit_date]
                return_pct = round(((exit_price - entry_price) / entry_price) * 100, 2)

                rows.append({
                    "pick_date": pick_date,
                    "symbol": symbol,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "return_pct": return_pct,
                    "momentum_score": row.get("momentum_score", ""),
                    "ai_score": row.get("ai_score", ""),
                    "final_score": row.get("final_score", ""),
                })
                print(f"  {symbol}: {entry_price:.2f} -> {exit_price:.2f} = {return_pct:+.2f}%")

            except Exception as e:
                print(f"  {symbol}: failed — {e}")

    if not rows:
        print("\nNo new returns to record.")
        return

    new_df = pd.DataFrame(rows)
    if Path(RETURNS_FILE).exists():
        new_df = pd.concat([pd.read_csv(RETURNS_FILE), new_df], ignore_index=True)

    new_df.to_csv(RETURNS_FILE, index=False)
    print(f"\nSaved {len(rows)} return records to {RETURNS_FILE}")

    # Summary stats
    if "return_pct" in new_df.columns:
        today_rows = new_df[new_df["pick_date"].isin(target_dates)]
        avg = today_rows["return_pct"].mean()
        win_rate = (today_rows["return_pct"] > 0).mean() * 100
        print(f"Avg return: {avg:+.2f}%  |  Win rate: {win_rate:.0f}%")


if __name__ == "__main__":
    main()
