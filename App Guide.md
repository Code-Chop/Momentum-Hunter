# Momentum Hunter — Complete Usage Guide

An AI-powered NSE stock scanner that scores 347 Nifty 500 stocks on momentum, runs Gemini AI conviction analysis, and delivers actionable entry/stop/target levels via Telegram. Designed to reduce daily trading decisions to a few bot commands.

---

## One-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env with your credentials
BOT_TOKEN=<your telegram bot token>
CHAT_ID=<your telegram chat id>
GEMINI_API_KEY=<your gemini api key>

# 3. Build the Nifty 500 stock universe (run once, ~10 min)
python build_universe.py

# 4. Start the bot — keep this running always
python telegram_bot.py
```

---

## How It Works

### 1. Scan
Scores every stock in the universe on:
- **Momentum returns** — 1M (40%), 3M (30%), 6M (20%), volatility (10%)
- **Trend filter** — stocks below 200 DMA are excluded before scoring
- **RSI adjustment** — overbought stocks penalised
- **Gemini AI conviction** — each top-20 stock rated 1–10 by Gemini with news context
- **Sector cap** — max 2 stocks per sector to prevent concentration

### 2. Decide
Combines live market data + scan results + real-time stock prices into one Gemini prompt. Returns:
- Should I trade today? (yes/no, with reason)
- Top 3 stocks with exact entry / stop / target
- Position size % adjusted for VIX level
- Entry time window

### 3. Market Regime (auto-protection)
| Condition | What happens |
|---|---|
| NIFTY below 200 DMA | Scan paused, `/decide` returns 🚫 SKIP |
| VIX > 25 | Top 5 picks only, smaller position size |
| VIX > 20 | Top 7 picks, cautious sizing |
| Stock flagged by Gemini as `avoid` | Excluded even if ranked #1 by score |

---

## Daily Workflow

### Swing Trader

```
Evening / Night
  /scan                    → full swing scan, picks sent to Telegram automatically

9:20 AM (market open)
  /decide swing            → live prices + AI decision, instant response

Place 2–3 limit orders from the /decide output. That's it.
```

### Intraday Trader

```
9:00–9:10 AM
  /scan intraday fast      → fast scan on top swing picks (~30s)

9:20 AM
  /decide intraday         → entry/stop/target for best 3 intraday setups

10:30 AM, 12:00 PM (optional refresh)
  /scan intraday fast      → re-scan with updated momentum
  /decide intraday         → fresh picks

3:00 PM
  Exit all intraday positions before 3:30 PM close
```

### Both (full workflow)

```
Evening       →  /scan                    (swing, daily closes, fine anytime)
9:00 AM       →  /scan intraday fast      (~30s, uses top swing picks as universe)
9:20 AM       →  /decide swing            (live prices)
              →  /decide intraday         (live prices)
Midday        →  /scan intraday fast      (optional refresh)
              →  /decide intraday
Friday eve    →  python track_returns.py  (log realized returns, 5 min)
```

> **Note:** Run `/decide` between 9:15 AM and 3:30 PM for live NSE prices. Outside market hours the bot falls back to last closing prices (still useful for evening planning, not for intraday execution).

---

## All Commands

### Scan Commands
| Command | What it does | Time |
|---|---|---|
| `/scan` | Full swing scan — all 347 stocks | ~5 min |
| `/scan intraday` | Full intraday scan — all 347 stocks | ~5 min |
| `/scan intraday fast` | Fast intraday scan — top 20 swing picks only | ~30–45s |

### Decision Commands
| Command | What it does | Time |
|---|---|---|
| `/decide` | AI decision for swing + intraday | ~20s |
| `/decide swing` | Swing only | ~20s |
| `/decide intraday` | Intraday only | ~20s |
| `/check` | Live NIFTY, Bank NIFTY, VIX, sectors | ~5s |

### Position Tracker Commands
| Command | What it does |
|---|---|
| `/add RELIANCE 2450` | Track position with auto stop/target |
| `/add RELIANCE 2450 2425 2499` | Track with custom stop and target |
| `/positions` | Live P&L for all open positions |
| `/exit RELIANCE` | Remove from tracking |
| `/exit all` | Clear all positions |

**Automatic alerts (no action needed):**
- Stop hit → immediate alert
- Target hit → immediate alert
- 3:00 PM → "30 min to close" reminder for all open positions
- 3:15 PM → urgent exit reminder
- 3:30 PM → auto-clears all positions

### Data Commands
| Command | What it does | Time |
|---|---|---|
| `/top5` | Latest swing picks (raw, no AI levels) | instant |
| `/intraday` | Latest intraday picks (raw) | instant |
| `/status` | Market regime + VIX + last scan times | instant |
| `/performance` | Backtest stats: CAGR, Sharpe, drawdown, win rate | instant |
| `/about` | Full app guide and workflow | instant |
| `/help` | Commands list | instant |

---

## Sample `/decide` Output

```
🧠 AI Decision — 01 Jun 09:20

📊 NIFTY50     : 24,580 (+0.33%) above 200DMA ✅
   India VIX   : 14.2 (-1.2%) ↓ easing

✅ TRADE — SWING
Confidence: 8/10 | Size: 3% per trade

📈 Take These Positions:
  1. RELIANCE
     Entry ₹2,450 → Stop ₹2,401 → Target ₹2,572
  2. HDFCBANK
     Entry ₹1,685 → Stop ₹1,651 → Target ₹1,769
  3. INFY
     Entry ₹1,925 → Stop ₹1,886 → Target ₹2,021

🚫 Skip: COALINDIA

💡 NIFTY above all MAs with declining VIX. Bank NIFTY leading — broad participation confirmed.
⚠️ Risk: US futures slightly red, watch first 15 min
⏰ Enter: 9:20–10:00 AM
```

---

## Kite Execution Guide

Your bot gives you:
```
RELIANCE
Entry ₹2,450 → Stop ₹2,401 → Target ₹2,572
Size: 3% per trade
```

Place **3 orders** in Kite. Here's exactly how.

### Step 1 — Buy (Entry)

Search the stock in Kite → click **BUY**

| Field | Value |
|---|---|
| Product | `MIS` ← intraday, required |
| Order type | `LIMIT` |
| Price | entry from bot |
| Qty | see formula below |

Wait for it to fill before placing the next two.

> **MIS = Margin Intraday Square-off.** Zerodha auto-exits any open MIS position at **3:20 PM**. The bot alerts you at 3:00 and 3:15 PM — always exit before Zerodha does it at market price.

### Step 2 — Stop Loss (place immediately after fill)

Search the stock again → click **SELL**

| Field | Value |
|---|---|
| Product | `MIS` |
| Order type | `SL-M` (Stop Loss Market) |
| Trigger price | stop from bot |

`SL-M` means: sell immediately at market price when the trigger is touched. Always fills even in fast drops — better than `SL` (Stop Limit) which can miss during a gap down.

### Step 3 — Target

Search the stock again → click **SELL**

| Field | Value |
|---|---|
| Product | `MIS` |
| Order type | `LIMIT` |
| Price | target from bot |

This sits in the order book and fills automatically when the stock reaches the target.

### After Either Order Fills

**If target hits** → go to Orders tab → cancel the SL-M order  
**If stop hits** → go to Orders tab → cancel the LIMIT target order

Kite does not cancel the other order automatically in regular orders. Forgetting this creates an accidental short position.

### Qty Formula

```
Qty = (Capital × position size%) ÷ entry price

Example: ₹5,00,000 × 3% ÷ ₹2,450 = 6 shares
```

### Easier Method: Bracket Order (BO)

Places all three legs (entry + stop + target) in one order. Kite cancels the remaining leg automatically.

1. Click BUY → change order type to **BO**
2. Fill in:

| Field | Value | Example |
|---|---|---|
| Price | entry | 2450 |
| Stop Loss | entry − stop (points) | 2450 − 2401 = **49** |
| Target | target − entry (points) | 2572 − 2450 = **122** |

No manual cancellation needed. Recommended once you're comfortable.

### Order Type Reference

| Type | When to use |
|---|---|
| `MIS` | All intraday orders — auto-exits at 3:20 PM |
| `CNC` | Delivery only — do NOT use for intraday |
| `LIMIT` | Fills at your price or better |
| `SL-M` | Triggers at price, fills at market — use for stop loss |
| `BO` | Bracket order — entry + stop + target in one |

---

## Paper Trading

Paper trading lets you track how the intraday scanner's picks would have performed without risking real money. Picks are logged automatically every time you run a scan **during market hours (09:15–15:30 IST)**. Scans run outside those hours are ignored.

### How it works

1. `intraday_main.py` runs a scan and picks the top 5 stocks
2. Each pick is saved to `app/data/paper_trades.csv` with the entry price at scan time
3. `evaluate_paper_trades.py` fetches the current price for each and calculates return

### Step 1 — Generate paper trades (run during market hours)

```bash
# Full scan — ~5 min
python intraday_main.py

# Fast scan — ~30s, uses top swing picks as universe
python intraday_main.py --fast
```

Runs the intraday scanner, sends the alert to Telegram, and appends the top 5 picks to `app/data/paper_trades.csv`. Only logs trades if run between 09:15–15:30 IST.

### Step 2 — Evaluate results (run anytime)

```bash
python evaluate_paper_trades.py
```

Fetches the latest price for every unique stock (first entry per symbol) and prints:

```
===== PAPER TRADING RESULTS =====
   symbol  entry_price  current_price  return_pct  score  ...
     ZEEL       106.25         114.80        8.05  117.87  ...
      SCI       319.35         298.10       -6.65  119.77  ...
  ...

Trades: 37
Win Rate: 43.24%
Average Return: 1.82%
```

Results are also saved to `app/data/paper_trade_results.csv`.

### Interpreting results

| Metric | What it means |
|---|---|
| Win Rate | % of picks that are currently profitable |
| Average Return | Mean return across all unique picks |
| above_vwap | Was the stock above its intraday VWAP at entry? True = stronger signal |
| breakout | Was the stock breaking out of its prior session range at entry? |

> **Context matters.** Always compare average return against Nifty's return over the same period. A -2% average in a -4% Nifty market is actually outperformance.

### Suggested routine

```
During market hours   →  python intraday_main.py --fast   (generates paper trades)
End of week           →  python evaluate_paper_trades.py  (see how picks did)
```

If win rate stays below 40% for 2+ weeks in a flat/up market, revisit the score weights in `config.py`.

---

## Weekly Review

```bash
# Log realized returns from the week's picks
python track_returns.py
```

Check `app/data/realized_returns.csv`. If win rate is below 50% for 2 consecutive weeks, halve your position size until it recovers.

---

## Minimal Daily Commitment

The absolute minimum to run this system:

```
Evening    →  /scan                  (2 min, set and forget)
9:20 AM    →  /decide swing          (read output, place 2–3 orders)
3:00 PM    →  exit intraday if any
Friday     →  python track_returns.py
```

**~5 minutes of active work per day.**
