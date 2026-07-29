import pandas as pd

from app.services.downloader import (
    StockDownloader
)


downloader = StockDownloader()


df = pd.read_csv("app/data/paper_trades.csv")

# Keep only the first entry per symbol (earliest timestamp)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").drop_duplicates(subset="symbol", keep="first")


results = []


for _, row in df.iterrows():

    symbol = row["symbol"]

    try:

        stock_df = (
            downloader.get_stock_data(
                symbol,
                period="5d"
            )
        )

        current_price = float(
            stock_df["Close"]
            .iloc[-1]
        )

        entry_price = float(
            row["entry_price"]
        )

        return_pct = (
            (
                current_price
                - entry_price
            )
            /
            entry_price
        ) * 100

        results.append(
            {
                "symbol": symbol,
                "entry_price": entry_price,
                "current_price": current_price,
                "return_pct": round(return_pct, 2),
                "score": row["score"],
                "ai_score": row.get("ai_score"),
                "volume_ratio": row["volume_ratio"],
                "breakout": row["breakout"],
                "above_vwap": row.get("above_vwap"),
                "entry_date": row["timestamp"],
            }
        )

    except Exception as e:

        print(
            symbol,
            e
        )


results_df = pd.DataFrame(
    results
)

if results_df.empty:
    print("\nNo paper trade results to evaluate.")
    exit()


print(
    "\n===== PAPER TRADING RESULTS =====\n"
)

print(
    results_df.sort_values(
        by="return_pct",
        ascending=False
    )
)


wins = len(
    results_df[
        results_df["return_pct"] > 0
    ]
)

win_rate = (
    wins
    / len(results_df)
) * 100


avg_return = (
    results_df[
        "return_pct"
    ].mean()
)


print(
    f"\nTrades: "
    f"{len(results_df)}"
)

print(
    f"Win Rate: "
    f"{win_rate:.2f}%"
)

print(
    f"Average Return: "
    f"{avg_return:.2f}%"
)


results_df.to_csv(
    "app/data/paper_trade_results.csv",
    index=False
)