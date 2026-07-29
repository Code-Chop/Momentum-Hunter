import pandas as pd

from app.services.downloader import (
    StockDownloader
)

from app.services.momentum import (
    MomentumCalculator
)

from app.services.portfolio_backtester import (
    PortfolioBacktester
)


downloader = StockDownloader()

momentum = MomentumCalculator()

backtester = (
    PortfolioBacktester(
        momentum
    )
)


stocks_df = pd.read_csv(
    "app/data/stocks.csv"
)

stocks = (
    stocks_df["symbol"]
    .tolist()
)


all_data = {}

print(
    "\nLoading NIFTY..."
)

all_data["NIFTY"] = (
    downloader.get_index_data(
        "^NSEI",
        period="5y"
    )
)

print(
    "\nDownloading stocks...\n"
)

for stock in stocks:

    try:

        print(
            f"Loading {stock}"
        )

        all_data[stock] = (
            downloader.get_stock_data(
                stock,
                period="5y"
            )
        )

    except Exception as e:

        print(
            stock,
            e
        )


print(
    "\nRunning Portfolio Backtest...\n"
)

results = (
    backtester.run_backtest(
        all_data,
        hold_days=5,
        top_n=10
    )
)

results.to_csv(
    "app/data/portfolio_backtest.csv",
    index=False
)

avg_return = (
    results[
        "portfolio_return"
    ].mean()
)

win_rate = (
    (
        results[
            "portfolio_return"
        ] > 0
    ).mean()
) * 100

best = (
    results[
        "portfolio_return"
    ].max()
)

worst = (
    results[
        "portfolio_return"
    ].min()
)

print(
    "\n===== PORTFOLIO BACKTEST =====\n"
)

print(
    f"Rebalances: "
    f"{len(results)}"
)

print(
    f"Average Return: "
    f"{avg_return:.2f}%"
)

print(
    f"Win Rate: "
    f"{win_rate:.2f}%"
)

print(
    f"Best Period: "
    f"{best:.2f}%"
)

print(
    f"Worst Period: "
    f"{worst:.2f}%"
)