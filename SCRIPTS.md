# Momentum Hunter — Script Reference

Complete guide to every Python file: what it does, when to run it, and what it produces.

---

## Daily Use (Run These Regularly)

---

### `main.py` — Swing Scanner
**When:** Once per day, after market close (3:30 PM+) or before market open.

Scans all ~500 Nifty500 stocks on multi-timeframe momentum (1M/3M/6M returns), applies 200 DMA and volume filters, then sends the top picks to Telegram with Gemini AI conviction scores.

**What it does step by step:**
1. Checks market regime (BULL / BEAR / VIX level) — adjusts how many picks to send
2. Downloads 1-year daily OHLCV for every stock via yfinance
3. Scores each stock: momentum returns + DMA filter + volume + 52-week high proximity + RSI
4. Sends top 20 to Gemini AI for conviction scoring (1–10)
5. Merges AI scores → final ranking
6. Applies sector cap (max 2 picks per sector)
7. Sends Telegram alert with top picks
8. Saves `app/data/final_ranking.csv` and `app/data/watchlist.csv`

**Output files:**
- `app/data/final_ranking.csv` — full ranked list (used by telegram_bot.py /top5)
- `app/data/watchlist.csv` — same, pre-AI scores
- `app/data/performance_log.csv` — today's top picks logged for return tracking

```
python main.py
```

---

### `intraday_main.py` — Intraday Scanner
**When:** During market hours (09:15–15:30 IST). Run every 30–60 minutes or on demand.

Scans all stocks using 15-minute OHLCV bars via Angel One (real-time) with yfinance fallback. Scores each stock on a normalized 0–100 composite and sends intraday picks to Telegram.

**What it does step by step:**
1. Checks market regime — switches to bear weights if NIFTY is below 200 DMA
2. Fetches Nifty 15-min data to compute today's index return (for RS alpha calculation)
3. For each stock: fetches 15-min bars, computes volume surge, return momentum, RS alpha vs Nifty, VWAP position, breakout above prior session high
4. Normalizes each signal to [-1, 1] scale, blends with weights → score maps to 0–100
5. Top 20 sent to Gemini with recent news headlines → conviction scores
6. Sector cap (max 2 per sector) applied to final top 5
7. Sends Telegram alert with entry levels, breakout/VWAP flags, RS alpha
8. Saves paper trade entries to `app/data/paper_trades.csv` (only during market hours)
9. Saves full watchlist to `app/data/intraday_watchlist.csv`

**Flags:**
- `--fast` — scans only the top 20 stocks from the last swing scan (~30s vs ~5 min)

**Output files:**
- `app/data/intraday_watchlist.csv` — full intraday ranked list
- `app/data/paper_trades.csv` — entry records for paper trade evaluation

```
python intraday_main.py          # full scan, all stocks (~5 min)
python intraday_main.py --fast   # top 20 swing picks only (~30s)
```

---

### `telegram_bot.py` — Interactive Telegram Bot
**When:** Run once, keep running continuously in the background.

A long-polling Telegram bot that responds to commands. Spawns scans as background subprocesses, monitors open positions for stop/target hits, and sends time-based exit reminders at 3:00 PM and 3:15 PM.

**Commands it handles:**

| Command | What it does |
|---|---|
| `/scan` | Triggers swing scan in background (~5 min) |
| `/scan intraday` | Triggers full intraday scan (~5 min) |
| `/scan intraday fast` | Triggers fast intraday scan (~30s) |
| `/decide` | AI decision: live market + picks → entry/stop/target for both swing and intraday |
| `/decide swing` | Swing-only decision |
| `/decide intraday` | Intraday-only decision |
| `/check` | Instant market pulse: NIFTY, BankNifty, VIX, sector indices (~5s, no AI) |
| `/top5` | Shows top 5 picks from the last swing scan |
| `/intraday` | Shows top 5 picks from the last intraday scan |
| `/add SYMBOL ENTRY` | Starts tracking a live position for stop/target alerts |
| `/add SYM ENTRY STOP TARGET` | Track with custom stop and target levels |
| `/positions` | Live P&L for all open tracked positions |
| `/exit SYMBOL` | Remove a position from tracking |
| `/exit all` | Clear all positions |
| `/status` | Market regime + VIX + when scans were last run |
| `/performance` | Backtest stats (CAGR, Sharpe, max drawdown) |
| `/liveperf` | Your actual live trade record stats |
| `/about` | Full workflow guide + Kite execution instructions |
| `/help` | Full command list |

**Position monitor:** background thread polls prices every 60s during market hours, fires alerts when stop or target is hit.

```
python telegram_bot.py
```

---

## After Market / Next Day

---

### `evaluate_paper_trades.py` — Paper Trade Evaluator
**When:** After market, or the next day. Requires `app/data/paper_trades.csv` to exist (written by intraday_main.py during market hours).

Reads logged intraday entries, fetches current prices, computes return for each pick. Deduplicates by keeping only the first entry per symbol.

**Output:**
- Prints a ranked results table to console (sorted by return %)
- Prints overall win rate and average return
- Saves `app/data/paper_trade_results.csv`

```
python evaluate_paper_trades.py
```

---

### `track_returns.py` — Swing Return Tracker
**When:** The morning after running `main.py`. Tracks next-day returns for swing picks.

Reads `app/data/performance_log.csv` (written by main.py), fetches 2 trading days of price data for each pick, computes entry-to-exit return (open day 1 → close day 2), and appends results to `app/data/realized_returns.csv`. Skips picks already tracked — safe to run multiple times.

**Output:**
- Prints per-pick returns to console
- Appends to `app/data/realized_returns.csv`
- Used by `/liveperf` command in the Telegram bot

```
python track_returns.py
```

---

### `performance_report.py` — Performance Summary
**When:** Anytime, after you have some tracking data built up.

Reads `app/data/realized_returns.csv` and prints a full performance breakdown: win rate, average return, expectancy, best/worst trade, streaks.

```
python performance_report.py
```

---

## One-Time Setup

---

### `build_universe.py` — Build Stock Universe
**When:** Once at initial setup, or when you want to refresh the Nifty500 list.

Downloads the current Nifty500 constituent list with sector tags and saves it to `app/data/stocks.csv`. This file is required by all scanners. Re-run every few months as index constituents change.

```
python build_universe.py
```

---

### `download_history.py` — Pre-download Historical Data
**When:** Once after building the universe, or before running backtests. Optional but speeds things up.

Downloads 1–5 years of daily OHLCV for every stock and caches it locally. Prevents rate-limit issues and makes backtests much faster.

```
python download_history.py
```

---

## Backtesting

---

### `portfolio_backtest.py` — Momentum Strategy Backtest
**When:** Run once to evaluate the swing strategy on historical data. Takes ~30 min (downloads 5 years of data for 500 stocks).

Simulates the momentum scanner over weekly rebalancing periods, tracks portfolio equity curve. Output powers the `/performance` Telegram command.

**Output:** `app/data/portfolio_backtest.csv`

```
python portfolio_backtest.py
```

---

### `ai_backtest.py` — Backtest with AI Scores
**When:** After running portfolio_backtest.py. Tests whether adding Gemini conviction scores improves returns vs pure momentum.

```
python ai_backtest.py
```

---

### `ai_ranking_backtest.py` — AI Ranking vs Momentum Ranking
**When:** After ai_backtest.py. Compares AI-ranked top picks vs momentum-only ranked picks side by side.

```
python ai_ranking_backtest.py
```

---

### `analyze_backtest.py` — Backtest Analyzer
**When:** After any backtest. Reads the output CSV and prints CAGR, Sharpe ratio, max drawdown, win rate, and other stats.

```
python analyze_backtest.py
```

---

## One-off Tests

---

### `ai_test.py` — Test Gemini Connection
Sends a minimal test prompt to Gemini and prints the response. Use this to verify your `GEMINI_API_KEY` is working.

```
python ai_test.py
```

---

### `gemini_test.py` — Test Gemini with Stock Prompt
Sends a sample stock analysis prompt to Gemini and prints the raw JSON response. Useful for debugging the AI layer.

```
python gemini_test.py
```

---

### `news_test.py` — Test News Fetching
Fetches recent headlines for a hardcoded symbol and prints them. Use this to verify the news service is working.

```
python news_test.py
```

---

## Internal Services (`app/services/`)

These are not run directly — they are imported by the scripts above.

| File | Role |
|---|---|
| `angel_one.py` | Angel One SmartAPI client — real-time LTP and 15-min candles for all stocks. Logs in once per day, caches session. |
| `downloader.py` | Central data fetcher — routes to Angel One (market hours) or yfinance (fallback/historical). Adds per-day file caching. |
| `intraday_scanner.py` | Computes the 0–100 normalized intraday score for a single stock's 15-min DataFrame. |
| `momentum.py` | Computes the swing momentum score (1M/3M/6M returns, DMA, volume, RSI, 52-week high). |
| `market_filter.py` | Determines market regime (BULL_LOW_VIX / BULL_HIGH_VIX / BULL_EXTREME_VIX / BEAR) using Nifty vs 200 DMA and India VIX. |
| `market_intelligence.py` | Fetches live index prices (Angel One → yfinance fallback), computes 50/200 DMA, formats market context for prompts and Telegram. |
| `decision_service.py` | The "should I trade today?" engine — combines live market snapshot + scan results + ATR-based levels → structured decision. |
| `report_builder.py` | Builds Gemini prompt strings for both swing and intraday scans, including metrics guide and regime context. |
| `ai_report_service.py` | Orchestrates the swing AI flow: builds prompt, calls Gemini, parses response. |
| `gemini_service.py` | Raw Gemini API wrapper — sends a prompt string, returns the text response. |
| `ai_parser.py` | Parses Gemini's JSON response into a structured dict. Handles malformed output gracefully. |
| `news_service.py` | Fetches recent news headlines for a stock symbol (used to enrich Gemini prompts). |
| `telegram_service.py` | Thin wrapper around the Telegram Bot API `sendMessage` endpoint. |
| `nse_live.py` | NSE.com browser cookie scraper — largely replaced by Angel One but still used by the position monitor in telegram_bot.py for live price checks. |
| `universe_builder.py` | Downloads Nifty500 constituents with sector metadata → `app/data/stocks.csv`. |
| `portfolio_backtester.py` | Backtesting engine used by portfolio_backtest.py — simulates weekly rebalancing over historical data. |
| `performance_tracker.py` | Saves today's top picks to `app/data/performance_log.csv` so track_returns.py can measure them later. |

---

## Data Files (`app/data/`)

| File | Written by | Read by |
|---|---|---|
| `stocks.csv` | build_universe.py | All scanners |
| `final_ranking.csv` | main.py | telegram_bot.py, intraday_main.py --fast |
| `watchlist.csv` | main.py | — |
| `intraday_watchlist.csv` | intraday_main.py | telegram_bot.py |
| `paper_trades.csv` | intraday_main.py | evaluate_paper_trades.py |
| `paper_trade_results.csv` | evaluate_paper_trades.py | — |
| `performance_log.csv` | main.py (via PerformanceTracker) | track_returns.py |
| `realized_returns.csv` | track_returns.py | telegram_bot.py /liveperf, performance_report.py |
| `portfolio_backtest.csv` | portfolio_backtest.py | analyze_backtest.py, telegram_bot.py /performance |
| `.cache/` | downloader.py | downloader.py (next call same day) |
| `.angel_session.pkl` | angel_one.py | angel_one.py (reused same day) |
| `.angel_tokens.pkl` | angel_one.py | angel_one.py (reused for 24h) |

---

## Typical Daily Workflow

```
Evening (after 3:30 PM):
  python main.py                      # swing scan → Telegram alert

Next morning (before 9:15 AM):
  python intraday_main.py --fast      # fast intraday scan using swing picks
  python track_returns.py             # record yesterday's swing returns

During market (09:15–15:30):
  python intraday_main.py --fast      # re-run every 30–60 min for fresh picks
  python telegram_bot.py              # OR keep this running and use /scan command

Anytime (Telegram bot running):
  /check       → instant market pulse
  /decide      → AI picks with entry/stop/target
  /add SYMBOL  → track a live position
  /positions   → see live P&L
```

Alternatively, run `telegram_bot.py` permanently and trigger everything from Telegram via `/scan`, `/decide`, and `/check`.
