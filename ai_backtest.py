"""
AI Backtest — Compare momentum-only vs AI-enhanced portfolio performance.

Uses performance_log.csv which stores both momentum_score and final_score
(momentum + AI conviction * 3) for each date's picks.

For each logged date:
  - Portfolio A: top 10 by momentum_score only
  - Portfolio B: top 10 by final_score (AI-enhanced ranking)
  - Downloads 5-day forward returns for each portfolio
  - Compares average return and win rate

Note: Both portfolios are drawn from the same pool of stocks saved on
each date, so the comparison reflects AI reranking within that pool.
Run main.py daily for several weeks to build up enough data points.
"""

import pandas as pd
from pathlib import Path
from app.services.downloader import StockDownloader

LOG_PATH = "app/data/performance_log.csv"
RESULTS_PATH = "app/data/ai_backtest_results.csv"
HOLD_DAYS = 5

downloader = StockDownloader()


def get_forward_return(symbol, entry_date, hold_days=HOLD_DAYS):
    try:
        df = downloader.get_stock_data(symbol, period="1y")
        future = df.loc[entry_date:]
        # Buy next day's close (no look-ahead bias)
        if len(future) <= hold_days + 1:
            return None
        buy = float(future["Close"].iloc[1])
        sell = float(future["Close"].iloc[hold_days + 1])
        return round(((sell - buy) / buy) * 100, 2)
    except Exception:
        return None


if not Path(LOG_PATH).exists():
    print(
        "\nNo performance log found. "
        "Run main.py first to generate picks."
    )
    exit()

log = pd.read_csv(LOG_PATH)
log["date"] = pd.to_datetime(log["date"])

dates = sorted(log["date"].unique())

print(f"\nPerformance log has {len(dates)} date(s).\n")

if len(dates) < 2:
    print(
        "Need at least 2 dates to compare. "
        "Keep running main.py daily — data accumulates automatically."
    )
    exit()

results = []

print(f"Evaluating {len(dates)} trading dates...\n")
print(
    f"{'Date':<12} | "
    f"{'Momentum':>10} | "
    f"{'AI-Enhanced':>12} | "
    f"{'AI Edge':>8}"
)
print("-" * 52)

for date in dates:

    picks = log[log["date"] == date].copy()

    if len(picks) < 5:
        continue

    # Two portfolios from the same saved picks
    mom_top = picks.nlargest(10, "momentum_score")["symbol"].tolist()
    ai_top = picks.nlargest(10, "final_score")["symbol"].tolist()

    all_symbols = list(set(mom_top + ai_top))

    # Fetch forward returns once per symbol
    forward_returns = {}
    for symbol in all_symbols:
        ret = get_forward_return(symbol, date)
        if ret is not None:
            forward_returns[symbol] = ret

    if len(forward_returns) < 5:
        continue

    mom_rets = [
        forward_returns[s]
        for s in mom_top
        if s in forward_returns
    ]

    ai_rets = [
        forward_returns[s]
        for s in ai_top
        if s in forward_returns
    ]

    if not mom_rets or not ai_rets:
        continue

    mom_avg = round(sum(mom_rets) / len(mom_rets), 2)
    ai_avg = round(sum(ai_rets) / len(ai_rets), 2)
    edge = round(ai_avg - mom_avg, 2)

    results.append(
        {
            "date": date,
            "momentum_return": mom_avg,
            "ai_return": ai_avg,
            "ai_edge": edge,
            "momentum_win": mom_avg > 0,
            "ai_win": ai_avg > 0,
        }
    )

    print(
        f"{str(date)[:10]:<12} | "
        f"{mom_avg:>+9.2f}% | "
        f"{ai_avg:>+11.2f}% | "
        f"{edge:>+7.2f}%"
    )


if not results:
    print(
        "\nCould not compute forward returns. "
        "Picks may be too recent — wait 5 trading days and re-run."
    )
    exit()

df_results = pd.DataFrame(results)
df_results.to_csv(RESULTS_PATH, index=False)

mom_avg_all = df_results["momentum_return"].mean()
ai_avg_all = df_results["ai_return"].mean()
mom_wr = df_results["momentum_win"].mean() * 100
ai_wr = df_results["ai_win"].mean() * 100
ai_edge_avg = df_results["ai_edge"].mean()

ai_better = (df_results["ai_edge"] > 0).sum()
mom_better = (df_results["ai_edge"] < 0).sum()

print("\n" + "=" * 52)
print("AI BACKTEST SUMMARY")
print("=" * 52)
print(f"Periods evaluated      : {len(df_results)}")
print()
print(f"Momentum-only avg      : {mom_avg_all:+.2f}%")
print(f"AI-enhanced avg        : {ai_avg_all:+.2f}%")
print()
print(f"Momentum-only win rate : {mom_wr:.1f}%")
print(f"AI-enhanced win rate   : {ai_wr:.1f}%")
print()
print(f"AI avg edge per period : {ai_edge_avg:+.2f}%")
print(f"Periods AI beat Momentum : {ai_better}/{len(df_results)}")
print(f"Periods Momentum beat AI : {mom_better}/{len(df_results)}")
print()

if ai_edge_avg > 0.1:
    print("Verdict: AI reranking is ADDING value ✅")
elif ai_edge_avg < -0.1:
    print("Verdict: Momentum-only outperforming AI reranking ⚠️")
else:
    print("Verdict: AI reranking is NEUTRAL (within noise) ➡️")

print(f"\nFull results saved to {RESULTS_PATH}")
