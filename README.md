# Momentum Hunter

An end-to-end algorithmic equity-momentum system for the Indian market (NSE). It scans the full Nifty 500, ranks stocks on multi-timeframe momentum, adds an LLM conviction layer, and delivers actionable picks — with entry/stop/target levels — straight to Telegram. It also tracks live positions, evaluates paper trades, and backtests the strategy over historical data.

> ⚠️ **Disclaimer:** This project is for educational and research purposes only. It is **not** financial advice and makes no guarantee of returns. Trading equities carries risk of loss. Use at your own risk, and validate everything independently before risking real capital.

---

## Highlights

- **Multi-timeframe momentum scanning** across ~500 NSE stocks (1M / 3M / 6M returns) with 200-DMA, volume, RSI, and 52-week-high filters.
- **Real-time intraday engine** on 15-minute bars via Angel One SmartAPI, with an automatic yfinance fallback and per-day caching.
- **LLM conviction layer** — top candidates are scored 1–10 by Gemini using price metrics and live news headlines, then blended with the quantitative score.
- **Market-regime awareness** — switches scoring weights based on Nifty vs 200-DMA and India VIX (bull / bear / high-VIX).
- **Interactive Telegram bot** — trigger scans, get AI decisions, track live positions with stop/target alerts, and pull performance stats from chat.
- **Backtesting suite** — weekly-rebalance simulation reporting CAGR, Sharpe, max drawdown, and win rate, plus AI-vs-momentum comparison backtests.
- **Free-hosted web dashboard + chat** — a Next.js frontend (Swing/Intraday views, About, and a chat interface that mirrors the Telegram bot's commands) backed by a FastAPI + Postgres (Supabase) API, with scans running as GitHub Actions jobs. Live at [momentum-hunter.vercel.app](https://momentum-hunter.vercel.app). See [Hosting](#hosting-free-tier) below.

### Backtest results

> Replace with your finalized figures and the exact window before publishing.

| Metric | Value |
|---|---|
| CAGR | **36.74%** |
| Max Drawdown | **-21.70%** |
| Win Rate | **64.15%** |
| Period | _5 years (update)_ |

---

## How it works

```
                ┌─────────────────────────────────────────────┐
                │              Stock Universe                  │
                │   build_universe.py → app/data/stocks.csv    │
                └───────────────────────┬─────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
     ┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
     │   Swing Scan    │      │  Intraday Scan   │      │    Backtests     │
     │    main.py      │      │ intraday_main.py │      │ portfolio_*.py   │
     └────────┬────────┘      └────────┬─────────┘      └────────┬─────────┘
              │                        │                         │
              ▼                        ▼                         ▼
     momentum scoring         15-min RS/VWAP/breakout      equity curve +
     + DMA/vol/RSI filters    scoring (0–100)              CAGR/Sharpe/DD
              │                        │
              └───────────┬────────────┘
                          ▼
              ┌───────────────────────┐
              │   Gemini LLM layer    │  conviction scores (1–10)
              │  + live news context  │  + sector cap (max 2/sector)
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │     Telegram Bot      │  alerts, /decide, position monitor
              │    telegram_bot.py    │  (60s stop/target polling)
              └───────────────────────┘
```

**Data sourcing:** `downloader.py` routes requests to Angel One during market hours (real-time LTP and 15-min candles) and falls back to yfinance for historical or off-hours data, with per-day file caching to avoid rate limits.

---

## Tech stack

- **Language:** Python (scanners, API), TypeScript/Next.js (dashboard)
- **Market data:** Angel One SmartAPI (real-time, local/optional), yfinance (historical / fallback, used everywhere in the cloud deployment)
- **AI:** Google Gemini (conviction scoring + decision reasoning)
- **Interface:** Telegram Bot API (long-polling) + a read-only web dashboard
- **Data / compute:** pandas, NumPy
- **Persistence:** Postgres (Supabase, cloud deployment) with CSV as a local-dev fallback; pickled session/token caches for Angel One (local only)
- **Scan execution:** GitHub Actions, manually dispatched (cloud deployment)

---

## Project structure

```
.
├── main.py                     # Swing scanner (daily)
├── intraday_main.py            # Intraday scanner (15-min bars)
├── telegram_bot.py             # Interactive Telegram bot (long-running)
├── evaluate_paper_trades.py    # Evaluate logged intraday paper trades
├── track_returns.py            # Track next-day swing returns
├── performance_report.py       # Performance summary from realized returns
├── build_universe.py           # Build the Nifty 500 universe
├── download_history.py         # Pre-cache historical OHLCV
├── portfolio_backtest.py       # Momentum strategy backtest
├── ai_backtest.py              # Backtest with AI scores
├── ai_ranking_backtest.py      # AI ranking vs momentum ranking
├── analyze_backtest.py         # Backtest stats (CAGR/Sharpe/DD)
│
└── app/
    ├── db.py                   # SQLAlchemy models + Postgres (Supabase) helpers
    ├── data/                   # CSV outputs + caches (generated, local fallback)
    └── services/
        ├── swing_scan_service.py   # run_swing_scan() — importable swing scan
        ├── intraday_scan_service.py # run_intraday_scan() — importable intraday scan
        ├── angel_one.py            # Angel One SmartAPI client (local/optional)
        ├── downloader.py           # Central data fetcher + cache
        ├── intraday_scanner.py     # 0–100 intraday scoring
        ├── momentum.py             # Swing momentum scoring
        ├── market_filter.py        # Market regime detection
        ├── market_intelligence.py  # Live index context
        ├── decision_service.py     # "Should I trade?" engine (ATR levels)
        ├── report_builder.py       # Gemini prompt construction
        ├── ai_report_service.py    # Swing AI orchestration
        ├── gemini_service.py       # Gemini API wrapper
        ├── ai_parser.py            # Robust JSON parsing of AI output
        ├── news_service.py         # News headline fetcher
        ├── telegram_service.py     # Telegram sendMessage wrapper
        ├── nse_live.py             # NSE live price fallback (dead code — unused)
        ├── universe_builder.py     # Nifty 500 constituents
        ├── portfolio_backtester.py # Backtest engine
        └── performance_tracker.py  # Logs picks for return tracking (CSV + Postgres)

├── api/                        # FastAPI read-only API (Render deployment)
│   ├── main.py                 # App instance, CORS
│   ├── routers/scans.py        # GET /api/swing/latest, /api/intraday/latest
│   └── schemas.py               # Pydantic response models
├── web/                         # Next.js dashboard (Vercel deployment)
│   └── app/{swing,intraday}/page.tsx
├── scripts/
│   └── init_db.py              # One-time Postgres table bootstrap
└── .github/workflows/
    ├── swing-scan.yml          # Swing scan job (manual dispatch)
    ├── intraday-scan.yml       # Intraday scan job (manual dispatch)
    └── keep-alive.yml          # Periodic ping so the free-tier API stays warm
```

---

## Getting started

### 1. Prerequisites

- Python 3.10+
- An Angel One SmartAPI account (API key + credentials)
- A Google Gemini API key
- A Telegram bot token and chat ID

### 2. Install

```bash
git clone https://github.com/<your-handle>/momentum-hunter.git
cd momentum-hunter
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file in the project root (adjust keys to match your code):

```env
# Gemini
GEMINI_API_KEY=your_gemini_key

# Angel One SmartAPI
ANGEL_API_KEY=your_api_key
ANGEL_CLIENT_ID=your_client_id
ANGEL_PASSWORD=your_pin
ANGEL_TOTP_SECRET=your_totp_secret

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

> Never commit `.env` or any `*.pkl` session/token files. Make sure they're in `.gitignore`.

### 4. Build the universe (one-time)

```bash
python build_universe.py        # → app/data/stocks.csv
python download_history.py      # optional: pre-cache OHLCV
```

---

## Usage

### Daily workflow

```bash
# Evening (after 3:30 PM) — swing scan → Telegram alert
python main.py

# Next morning (before 9:15 AM)
python intraday_main.py --fast   # fast intraday scan on swing picks
python track_returns.py          # record yesterday's swing returns

# During market hours (09:15–15:30)
python intraday_main.py --fast   # re-run every 30–60 min for fresh picks
```

### Or run everything from Telegram

Keep the bot running and drive the whole system from chat:

```bash
python telegram_bot.py
```

**Bot commands**

| Command | Description |
|---|---|
| `/scan` | Run a swing scan in the background |
| `/scan intraday [fast]` | Run a full or fast intraday scan |
| `/decide [swing\|intraday]` | AI decision: live market + picks → entry / stop / target |
| `/check` | Instant market pulse (NIFTY, BankNifty, VIX, sectors) |
| `/top5` · `/intraday` | Top picks from the last swing / intraday scan |
| `/add SYMBOL ENTRY [STOP TARGET]` | Track a live position for alerts |
| `/positions` | Live P&L for all tracked positions |
| `/exit SYMBOL` · `/exit all` | Stop tracking a position |
| `/status` | Market regime, VIX, last scan times |
| `/performance` · `/liveperf` | Backtest stats / live trade record |
| `/help` · `/about` | Command list and full workflow guide |

A background thread polls open positions every 60 seconds during market hours and fires an alert when a stop or target is hit, plus time-based exit reminders late in the session.

---

## Backtesting

```bash
python portfolio_backtest.py     # simulate the momentum strategy (~5 yrs)
python ai_backtest.py            # does the Gemini layer add value?
python ai_ranking_backtest.py    # AI ranking vs momentum ranking
python analyze_backtest.py       # CAGR / Sharpe / max drawdown / win rate
```

---

## Hosting (free tier)

**Live demo:** [momentum-hunter.vercel.app](https://momentum-hunter.vercel.app)

The scanners, a read-only + chat API, and a web dashboard run entirely on free tiers.

| Layer | Service | Role |
|---|---|---|
| Database | [Supabase](https://supabase.com) free Postgres | Stores `swing_ranking`, `intraday_watchlist`, `performance_log`, `chat_message` |
| Scan execution | GitHub Actions (`.github/workflows/*.yml`) | Runs `main.py` / `intraday_main.py --fast`, writes to Postgres, and sends the Telegram alert directly. Triggered manually (Actions tab, or chat's `/scan`) — see note below on why there's no cron |
| API | [Render](https://render.com) free web service (FastAPI, `api/`) | `GET /api/swing/latest`, `GET /api/intraday/latest` for the dashboard, plus `/api/chat/*` for the web chat (see below) |
| Dashboard | [Vercel](https://vercel.com) free tier (Next.js, `web/`) | Landing page, Swing/Intraday views, About, and Chat |

### Web chat (`/chat`)

A browser-based command interface backed by `app/chat_commands.py`, which reuses the exact same scan scripts and services as `telegram_bot.py` — so `/top5`, `/intraday`, `/status`, `/check` work identically to the bot, and `/scan` / `/scan intraday [fast]` runs a real scan as a background subprocess on the API server, posting the result into chat history when done.

`/scan` is gated behind `CHAT_ACCESS_TOKEN` (sent as an `X-Chat-Token` header) so a public deployment can't have its Gemini/yfinance quota run up by strangers — read commands stay open for anyone to try. Both GitHub Actions and chat's `/scan` trigger the same scripts, but they run in different places, and that matters: an Actions job runs on GitHub's own runners with a 6-hour budget and no idle-sleep, whereas chat's `/scan` spawns the scan as a subprocess on the Render instance itself — where a multi-minute run could in principle be interrupted if the free tier suspends the instance mid-scan. Chat's version is the convenient one; the Actions job is the reliable one.

### Setup

1. **Supabase**: create a free project, copy the *pooled* connection string (Supavisor, port 6543, transaction mode — not the direct 5432 connection). Run `DATABASE_URL=... python scripts/init_db.py` once to create tables.
2. **GitHub Actions**: repo secrets `DATABASE_URL`, `BOT_TOKEN`, `CHAT_ID`, `GEMINI_API_KEY`. Trigger a run from the Actions tab (`workflow_dispatch`) or via chat's `/scan`.

   Both workflows are **manual-dispatch only** — deliberately. A `schedule:` block would make the dashboard self-updating, but this is a demo deployment, and an unattended daily cron spends Gemini quota (and hammers yfinance from a datacenter IP) whether or not anyone is looking at the results. The cron expressions are left in the workflow comments; uncommenting them is the whole change. The trade-off is that data is only as fresh as the last manual run.
3. **Render**: new free Web Service, start command `uvicorn api.main:app --host 0.0.0.0 --port $PORT` (see `Procfile`). Env vars needed:
   - `DATABASE_URL` — same Supabase connection string
   - `CORS_ALLOW_ORIGINS` — your Vercel URL, e.g. `https://momentum-hunter.vercel.app`
   - `CHAT_ACCESS_TOKEN` — a password of your choosing, gates `/scan` in the chat
   - `BOT_TOKEN`, `CHAT_ID`, `GEMINI_API_KEY` — **required even here**, not just in GitHub Actions, because chat's `/scan` runs `main.py`/`intraday_main.py` as a subprocess on Render itself, using Render's own environment
   - Do **not** set `ANGEL_*` vars in the cloud deployment — see limitations below
4. **Vercel**: import the repo with root directory `web/`, set `NEXT_PUBLIC_API_BASE_URL` to your Render URL.

### Known limitations of the free-hosted deployment

- **Cold starts**: Render's free tier sleeps after ~15 min idle; the first dashboard visit after a gap can take 30-50s. `keep-alive.yml` pings `/health` every 10 minutes during waking hours to blunt this — deliberately not round-the-clock, since the free tier's 750 instance-hours/month is barely more than a month's 730 hours.
- **Angel One disabled in the cloud**: the swing scan never used it anyway; the intraday scan silently falls back to yfinance. Re-enabling it would need session-token persistence in Postgres instead of local pickle files (not implemented).
- **`/performance` and `/liveperf` commands stay local-only**: they depend on `portfolio_backtester.py` / `track_returns.py`, which aren't part of the automated cloud pipeline.
- **`telegram_bot.py` itself is not rearchitected for cloud hosting** — it still runs via local long-polling if you want it. The cloud pipeline sends Telegram alerts directly (via `requests`) without needing an always-on bot process, and the web chat covers the same read commands + `/scan` for anyone browsing the live site.
- **yfinance from datacenter IPs** (GitHub Actions/Render) can be rate-limited more aggressively than from residential IPs — expect the occasional thin/empty scan.

---

## Roadmap

- [ ] Broker order execution (currently manual / paper)
- [ ] Telegram bot webhook mode + Postgres-backed position monitor (so the bot itself can be cloud-hosted too)
- [ ] Angel One session persistence in Postgres (re-enable live data in the cloud)
- [ ] Expanded universe beyond Nifty 500
- [ ] Walk-forward / out-of-sample validation

---

## License

Released under the MIT License. See `LICENSE` for details.