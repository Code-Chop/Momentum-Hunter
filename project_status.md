# Momentum Hunter - Project Status

## Project Goal

Build an AI-enhanced stock selection system for Indian equities that:

* Scans a filtered NSE universe
* Ranks stocks using momentum
* Uses AI to refine selections
* Produces actionable daily watchlists
* Tracks performance over time
* Later expands into intraday scanning

---

# Current Architecture

Universe Builder
↓
Filtered Stock Universe
↓
Momentum Engine
↓
Top Candidates
↓
News Collection
↓
Gemini Analysis
↓
AI Conviction Scores
↓
Final Ranking
↓
Telegram Delivery

---

# Current Universe

Source:

* Nifty 500 Constituents

Current Filters:

* Price > ₹50
* Average Volume > 500,000
* Average Daily Traded Value > ₹5 Crore

Current Universe Size:

* 347 Stocks

Files:

* app/services/universe_builder.py
* build_universe.py

Output:

* app/data/stocks.csv

---

# Momentum Engine

File:

* app/services/momentum.py

Formula:

score =
1M_return * 0.30

* 3M_return * 0.30
* 6M_return * 0.30
* volume_score * 0.10

Additional Rule:

* If current price < 50 DMA:
  -20 score penalty

Output:

* Momentum score per stock

---

# AI Layer

Model:

* Gemini 2.5 Flash

Pipeline:

Top 20 Momentum Stocks
↓
News Headlines
↓
Prompt Builder
↓
Gemini
↓
Structured JSON Response

Output Format:

{
"stocks": [
{
"symbol": "XYZ",
"conviction": 9.0
}
],
"highest_conviction": "XYZ",
"highest_risk": "ABC",
"avoid": "DEF",
"market_sentiment": "Bullish"
}

---

# Final Ranking

Formula:

final_score =
momentum_score
+
(ai_conviction * 3)

Ranking is sorted by:

* final_score descending

Output:

* Top 10 Final Picks

---

# Telegram Integration

File:

* app/services/telegram_service.py

Current Telegram Report:

📈 Momentum Hunter Final Picks

Top 10 Ranked Stocks

🏆 Highest Conviction

⚠️ Highest Risk

🚫 Avoid

📊 Market Sentiment

---

# Performance Tracking

File:

* app/services/performance_tracker.py

Stores:

date
symbol
momentum_score
ai_score
final_score

Output:

* app/data/performance_log.csv

Status:

* Working

---

# Backtesting

## Original Stock-Level Backtest

Result:

Trades: 1000
Average Return: 1.27%
Win Rate: 52%

Observation:

* Tested individual stocks
* Did NOT test Momentum Hunter strategy

---

## Portfolio Backtest (Current)

Strategy:

Every 5 Trading Days:

1. Calculate momentum scores
2. Rank stocks
3. Select Top 10
4. Equal Weight Portfolio
5. Hold 5 Trading Days
6. Measure portfolio return

Results:

Rebalances: 221

Average Return: 2.31%

Win Rate: 58.82%

Best Period: 44.40%

Worst Period: -13.68%

Observation:

Momentum ranking significantly outperformed the original stock-level backtest.

---

# Current Working Files

main.py

build_universe.py

portfolio_backtest.py

app/services/

* downloader.py
* universe_builder.py
* momentum.py
* news_service.py
* gemini_service.py
* ai_report_service.py
* ai_parser.py
* telegram_service.py
* performance_tracker.py
* portfolio_backtester.py

---

# Immediate Next Priorities

Priority 1:
Backtest Analytics

Goals:

* Equity Curve
* CAGR
* Total Return
* Max Drawdown
* Best/Worst Year

---

Priority 2:
Market Regime Filter

Rule:

Only enter positions when:

NIFTY > 200 DMA

Goal:

* Improve win rate
* Reduce drawdowns

---

Priority 3:
Stock Trend Filter

Rule:

Only buy stocks above their own 200 DMA

Goal:

* Improve quality of momentum selections

---

Priority 4:
AI Backtest

Compare:

Momentum Only

vs

Momentum + AI Ranking

Goal:

* Quantify AI contribution

---

Priority 5:
Intraday Scanner

New File:

* app/services/intraday_scanner.py

Requirements:

* 15 minute candles
* Volume spike detection
* Breakout detection
* VWAP filter
* Relative strength
* Top 20 opportunities
* Telegram integration

Future Pipeline:

347 Stocks
↓
15m Data
↓
Intraday Score
↓
Top 20
↓
News
↓
Gemini
↓
Top Intraday Picks

---

# Long-Term Vision

Daily Swing Scanner
+
Intraday Scanner
+
Performance Analytics
+
Automated Ranking
+
AI Decision Layer

Goal:
Create a systematic stock-selection platform capable of identifying high-probability swing and intraday opportunities in Indian markets.
