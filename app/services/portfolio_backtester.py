import pandas as pd
from app.services.market_filter import (
    MarketFilter
)
from config import USE_NIFTY_FILTER

class PortfolioBacktester:

    def __init__(self, momentum_calculator):

        self.momentum = (
            momentum_calculator
        )
        self.market_filter = (
            MarketFilter()
        )
        
    def run_backtest(
        self,
        all_data,
        hold_days=5,
        top_n=10
    ):

        results = []

        # Use NIFTY timeline as master timeline
        dates = (
            all_data["NIFTY"].index
        )

        for i in range(
            200,
            len(dates) - hold_days,
            5
        ):

            current_date = dates[i]

            # =====================
            # MARKET FILTER
            # =====================

            nifty_df = (
                all_data["NIFTY"]
            )

            market_history = (
                nifty_df.loc[:current_date]
            )

            if len(market_history) < 200:

                continue

            dma_200 = float(
                market_history["Close"]
                .rolling(200)
                .mean()
                .iloc[-1]
            )

            current_nifty = float(
                market_history["Close"]
                .iloc[-1]
            )

            if USE_NIFTY_FILTER:
                if current_nifty < dma_200:
                    continue

            # =====================
            # SCORE STOCKS
            # =====================

            scores = []

            for symbol, df in all_data.items():

                if symbol == "NIFTY":

                    continue

                try:

                    history = (
                        df.loc[:current_date]
                    )

                    score = (
                        self.momentum
                        .calculate_score(
                            history
                        )
                    )

                    if score is not None:

                        scores.append(
                            {
                                "symbol": symbol,
                                "score": score
                            }
                        )

                except Exception:

                    continue

            if len(scores) < top_n:

                continue

            ranking = pd.DataFrame(
                scores
            )

            ranking = (
                ranking.sort_values(
                    by="score",
                    ascending=False
                )
            )

            top_stocks = (
                ranking.head(top_n)
            )

            # =====================
            # PORTFOLIO RETURN
            # =====================

            portfolio_returns = []

            for _, row in (
                top_stocks.iterrows()
            ):

                symbol = (
                    row["symbol"]
                )

                stock_df = (
                    all_data[symbol]
                )

                try:

                    future_data = (
                        stock_df.loc[
                            current_date:
                        ]
                    )

                    # Need scoring day + hold_days + 1 extra (buy next day)
                    if (
                        len(future_data)
                        <= hold_days + 1
                    ):

                        continue

                    # Buy at next trading day's close (avoid look-ahead bias)
                    buy_price = float(
                        future_data[
                            "Close"
                        ].iloc[1]
                    )

                    sell_price = float(
                        future_data[
                            "Close"
                        ].iloc[hold_days + 1]
                    )

                    return_pct = (
                        (
                            sell_price
                            - buy_price
                        )
                        / buy_price
                    ) * 100

                    portfolio_returns.append(
                        return_pct
                    )

                except Exception:

                    continue

            if not portfolio_returns:

                continue

            avg_return = (
                sum(portfolio_returns)
                / len(
                    portfolio_returns
                )
            )

            results.append(
                {
                    "date": current_date,
                    "portfolio_return": (
                        avg_return
                    )
                }
            )

        return pd.DataFrame(
            results
        )