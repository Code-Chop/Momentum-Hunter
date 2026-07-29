import pandas as pd


df = pd.read_csv(
    "app/data/portfolio_backtest.csv"
)
df["date"] = pd.to_datetime(
    df["date"]
)

# =====================
# EQUITY CURVE
# =====================

capital = 100000

equity_curve = []

for ret in df["portfolio_return"]:

    capital *= (
        1 + ret / 100
    )

    equity_curve.append(
        capital
    )

df["equity"] = equity_curve

# =====================
# RETURNS
# =====================

final_capital = (
    df["equity"].iloc[-1]
)

total_return = (
    (
        final_capital
        / 100000
    )
    - 1
) * 100

start_date = (
    df["date"].min()
)

end_date = (
    df["date"].max()
)

years = (
    end_date - start_date
).days / 365.25

print("\n===== CAGR DEBUG =====\n")

print(start_date)
print(end_date)
print(years)

cagr = (
    (
        final_capital
        / 100000
    )
    ** (1 / years)
    - 1
) * 100

# =====================
# DRAWDOWN
# =====================

rolling_max = (
    df["equity"]
    .cummax()
)

drawdown = (
    (
        df["equity"]
        - rolling_max
    )
    / rolling_max
) * 100

max_drawdown = (
    drawdown.min()
)

# =====================
# WIN RATE
# =====================

wins = len(
    df[
        df["portfolio_return"] > 0
    ]
)

win_rate = (
    wins
    / len(df)
) * 100

# =====================
# SHARPE RATIO
# =====================

# Rebalance every 5 trading days ≈ 52 periods/year
# Risk-free rate: 6.5% annualized → 6.5/52 = 0.125% per period
RISK_FREE_PER_PERIOD = 6.5 / 52

mean_ret = df["portfolio_return"].mean()
std_ret = df["portfolio_return"].std()

sharpe = (
    (mean_ret - RISK_FREE_PER_PERIOD)
    / std_ret
    * (52 ** 0.5)
    if std_ret > 0
    else 0.0
)

# =====================
# BEST / WORST
# =====================

best_trade = (
    df["portfolio_return"]
    .max()
)

worst_trade = (
    df["portfolio_return"]
    .min()
)

# =====================
# YEARLY ANALYSIS
# =====================

df["date"] = pd.to_datetime(
    df["date"]
)

df["year"] = (
    df["date"]
    .dt.year
)

yearly = (
    df.groupby("year")
    ["portfolio_return"]
    .mean()
)

# =====================
# REPORT
# =====================

print(
    "\n===== PERFORMANCE REPORT =====\n"
)

print(
    f"Rebalances: {len(df)}"
)

print(
    f"Final Capital: Rs{final_capital:,.0f}"
)

print(
    f"Total Return: {total_return:.2f}%"
)

print(
    f"CAGR: {cagr:.2f}%"
)

print(
    f"Max Drawdown: {max_drawdown:.2f}%"
)

print(
    f"Win Rate: {win_rate:.2f}%"
)

print(
    f"Best Trade: {best_trade:.2f}%"
)

print(
    f"Worst Trade: {worst_trade:.2f}%"
)

print(
    f"Sharpe Ratio: {sharpe:.2f}"
)

print(
    "\n===== YEARLY AVG RETURNS =====\n"
)

print(yearly)

# Save report data

df.to_csv(
    "app/data/performance_report.csv",
    index=False
)