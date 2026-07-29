import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv(
    "app/data/portfolio_backtest.csv"
)

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
print(df.head())

print(df.tail())


total_return = (
    (
        capital
        / 100000
    )
    - 1
) * 100


first_date = pd.to_datetime(df["date"].iloc[0])
last_date = pd.to_datetime(df["date"].iloc[-1])
years = (last_date - first_date).days / 365.25

cagr = (
    (
        capital
        / 100000
    )
    ** (1 / years)
    - 1
) * 100


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


print(
    "\n===== ANALYTICS =====\n"
)

print(
    f"Rebalances: {len(df)}"
)

print(
    f"Final Capital: "
    f"₹{capital:,.0f}"
)

print(
    f"Total Return: "
    f"{total_return:.2f}%"
)

print(
    f"CAGR: "
    f"{cagr:.2f}%"
)

print(
    f"Max Drawdown: "
    f"{max_drawdown:.2f}%"
)

plt.figure(
    figsize=(10, 5)
)

plt.plot(
    df["equity"]
)

plt.title(
    "Momentum Hunter Equity Curve"
)

plt.xlabel(
    "Rebalance"
)

plt.ylabel(
    "Portfolio Value"
)

plt.grid()

plt.show()