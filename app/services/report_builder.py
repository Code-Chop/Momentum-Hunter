class ReportBuilder:

    def _regime_context(self, regime, vix):
        """Return a one-line market context string for AI prompts, or empty string if unknown."""
        if not regime:
            return ""
        vix_part = f", India VIX={vix}" if vix else ""
        picks_hint = {
            "BULL_LOW_VIX":     "Normal conditions — rank freely.",
            "BULL_HIGH_VIX":    "Elevated fear — favour defensive, high-quality names.",
            "BULL_EXTREME_VIX": "Extreme fear — only the strongest setups qualify.",
            "BEAR":             "Bear market — extra caution required.",
        }.get(regime, "")
        return f"\nMarket regime: {regime}{vix_part}. {picks_hint}\n"

    def build_intraday_prompt(self, ranking_df, news_data, regime=None, vix=None):

        prompt = (
            "You are an expert intraday trader for Indian equities (NSE).\n"
            + self._regime_context(regime, vix)
            + """
Analyze these top intraday candidates and return ONLY valid JSON.

Format:

{
"stocks": [
    {
    "symbol": "STOCK_NAME",
    "conviction": 8.5
    }
],

"highest_conviction": "STOCK_NAME",

"avoid": "STOCK_NAME",

"market_sentiment": "Bullish"
}

Definitions:

highest_conviction:
Best intraday opportunity with strong technicals
and positive news catalyst.

avoid:
Stock with technical setup but negative news,
earnings risk, or red flags — skip for today.

market_sentiment:
Bullish, Neutral or Bearish for intraday session.

Rules:

- conviction must be between 1 and 10
- rank stocks from best to worst intraday opportunity
- return top 10 stocks only
- output ONLY JSON

Metrics guide:
- score: normalized 0-100 composite (50=neutral, >65=strong setup)
- volume_ratio: recent vs 20-bar average (>2 = strong conviction)
- return_pct: % change from previous 15-min bar
- breakout: True if price broke above prior session's high
- above_vwap: True if price above intraday VWAP
- rs_vs_nifty: alpha vs NIFTY today in % (positive = outperforming Nifty)
"""
        )

        for _, row in ranking_df.iterrows():
            symbol = row["symbol"]
            prompt += (
                f"\n\n{symbol}"
                f"\nScore: {row['score']}"
                f"\nVolume Ratio: {row['volume_ratio']}x"
                f"\nReturn: {row['return_pct']}%"
                f"\nBreakout: {row['breakout']}"
                f"\nAbove VWAP: {row['above_vwap']}"
                f"\nRS vs NIFTY: {row.get('rs_vs_nifty', 'N/A')}"
            )
            if symbol in news_data:
                prompt += "\nRecent Headlines:"
                for headline in news_data[symbol]:
                    prompt += f"\n- {headline}"

        return prompt

    def build_watchlist_prompt(self, ranking_df, news_data, regime=None, vix=None):

        prompt = (
            "You are an expert Indian stock market analyst.\n"
            + self._regime_context(regime, vix)
            + """
Analyze the stocks and return ONLY valid JSON.

Format:

{
"stocks": [
    {
    "symbol": "STOCK_NAME",
    "conviction": 8.5
    }
],

"highest_conviction": "STOCK_NAME",

"highest_risk": "STOCK_NAME",

"avoid": "STOCK_NAME",

"market_sentiment": "Bullish"
}

Definitions:

highest_conviction:
Stock with strongest combination of momentum,
fundamentals and news.

highest_risk:
Stock with highest upside potential but also
highest downside risk and volatility.

avoid:
Stock that should be avoided despite momentum,
due to poor news, weak fundamentals or elevated risk.

market_sentiment:
Bullish, Neutral or Bearish.

Rules:

- conviction must be between 1 and 10
- rank stocks from best to worst
- return top 10 stocks only
- output ONLY JSON

Do not select the same stock for
highest_conviction and avoid.

Avoid should be the weakest candidate
among the analyzed stocks.
"""
        )

        for _, row in ranking_df.iterrows():
            symbol = row["symbol"]
            prompt += f"\n\n{symbol}\nMomentum Score: {row['score']}"
            if symbol in news_data:
                prompt += "\nRecent Headlines:"
                for headline in news_data[symbol]:
                    prompt += f"\n- {headline}"

        return prompt
