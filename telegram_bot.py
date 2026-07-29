"""
Interactive Telegram Bot for Momentum Hunter.

Commands:
  /decide          — Full AI decision: should I trade, which picks, entry/stop/target
  /decide swing    — Swing-only decision
  /decide intraday — Intraday-only decision
  /check           — Instant market pulse (NIFTY, VIX, sectors) — no AI, ~5s
  /top5            — Today's top 5 swing picks (from last scan)
  /intraday        — Today's top 5 intraday picks (from last scan)
  /performance     — Backtest stats (CAGR, Sharpe, drawdown)
  /status          — Market regime + India VIX
  /help            — List all commands

Run once, keep running in background:
    python telegram_bot.py
"""

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import math
import sys
import time
import threading
import subprocess
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

from app.logger import get_logger
from app.services.market_filter import MarketFilter
from app.services.market_intelligence import MarketIntelligence
from app.services.decision_service import DecisionService
from app.services.angel_one import get_angel_one
from config import (
    BOT_TOKEN, CHAT_ID,
    DECISION_INTRADAY_STOP_PCT, DECISION_INTRADAY_TARGET_PCT,
)

logger = get_logger("telegram_bot")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Prevent two scans of the same type running simultaneously
_scan_running = {"swing": False, "intraday": False}

# ── Intraday position tracker ─────────────────────────────────────────
# {SYMBOL: {entry, stop, target, added_at, alerted_stop, alerted_target}}
_positions   = {}
_pos_lock    = threading.Lock()
_pos_chat_id = None   # chat to send price alerts to


def _position_monitor():
    """
    Background thread: polls NSE prices every 60s during market hours.
    Fires stop/target alerts and time-based exit reminders.
    No Gemini calls — pure rule-based price watching.
    """
    ao           = get_angel_one()
    alerted_3pm  = False
    alerted_315  = False
    last_date    = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # Reset daily state at start of each new day
            if today != last_date:
                alerted_3pm = alerted_315 = False
                last_date   = today
                with _pos_lock:
                    if _positions:
                        logger.info("New day — clearing %d stale positions", len(_positions))
                        _positions.clear()

            in_market = (
                now.replace(hour=9,  minute=15, second=0) <=
                now <=
                now.replace(hour=15, minute=30, second=0)
            )

            with _pos_lock:
                has_pos  = bool(_positions)
                syms     = list(_positions.keys())
                chat_id  = _pos_chat_id

            if not (in_market and has_pos and chat_id):
                time.sleep(60)
                continue

            # ── 3:00 PM — 30-min warning ─────────────────────────────
            if now.hour == 15 and now.minute < 15 and not alerted_3pm:
                alerted_3pm = True
                with _pos_lock:
                    open_syms = list(_positions.keys())
                if open_syms:
                    send(chat_id,
                         f"⏰ 30 min to close!\n"
                         f"Open: {', '.join(open_syms)}\n"
                         f"Plan exits — market closes 3:30 PM.")

            # ── 3:15 PM — urgent warning ──────────────────────────────
            if now.hour == 15 and now.minute >= 15 and not alerted_315:
                alerted_315 = True
                with _pos_lock:
                    open_syms = list(_positions.keys())
                if open_syms:
                    send(chat_id, f"🚨 15 min to close! EXIT NOW: {', '.join(open_syms)}")

            # ── 3:30 PM — auto-clear ──────────────────────────────────
            if now.hour == 15 and now.minute >= 30:
                with _pos_lock:
                    if _positions:
                        send(chat_id, "🔔 Market closed. Cleared all tracked positions.")
                        _positions.clear()
                time.sleep(60)
                continue

            # ── Price-based stop / target alerts ─────────────────────
            quotes = ao.get_ltp_bulk(syms)

            with _pos_lock:
                for sym in list(_positions.keys()):
                    pos   = _positions[sym]
                    price = quotes.get(sym.upper())
                    if price is None:
                        continue

                    price = float(price)
                    pnl   = round(((price - pos["entry"]) / pos["entry"]) * 100, 2)

                    if price <= pos["stop"] and not pos["alerted_stop"]:
                        pos["alerted_stop"] = True
                        send(chat_id,
                             f"🔴 STOP HIT — {sym}\n"
                             f"Price ₹{price} hit stop ₹{pos['stop']}\n"
                             f"P&L: {pnl:+.2f}% | EXIT NOW")

                    elif price >= pos["target"] and not pos["alerted_target"]:
                        pos["alerted_target"] = True
                        send(chat_id,
                             f"🟢 TARGET HIT — {sym}\n"
                             f"Price ₹{price} reached target ₹{pos['target']}\n"
                             f"P&L: {pnl:+.2f}% | Book profit or trail stop")

        except Exception as e:
            logger.error("Position monitor error: %s", e)

        time.sleep(60)


# ==========================================
# TELEGRAM HELPERS
# ==========================================

def send(chat_id, text):
    try:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception as e:
        logger.error("Send error: %s", e)


def get_updates(offset=None):
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=35)
        return r.json()
    except Exception:
        return {"result": []}


# ==========================================
# COMMAND HANDLERS
# ==========================================

def cmd_decide(chat_id, args=""):
    """
    Full AI decision: live market + latest scan + Gemini.
    Args: "swing" | "intraday" | "" (both)
    Takes ~15-20 seconds due to yfinance + Gemini calls.
    Runs in a background thread so the bot loop stays responsive.
    """
    mode_map = {"swing": "swing", "intraday": "intraday"}
    mode = mode_map.get(args.strip().lower(), "both")

    send(chat_id, "⏳ Analyzing market conditions... (15-20s)")

    def run():
        try:
            svc      = DecisionService()
            decision = svc.get_decision(mode=mode)
            snapshot = svc.intelligence.get_index_snapshot()
            message  = DecisionService.format_message(decision, snapshot)
            send(chat_id, message)
        except Exception as e:
            logger.error("Decision failed: %s", e)
            send(chat_id, f"❌ Decision error: {e}\nTry again or check logs.")

    threading.Thread(target=run, daemon=True).start()


def cmd_check(chat_id):
    """
    Instant market pulse — NIFTY, Bank NIFTY, VIX, sectors.
    No Gemini call, responds in ~5 seconds.
    """
    send(chat_id, "⏳ Fetching market data...")

    def run():
        try:
            intel    = MarketIntelligence()
            snapshot = intel.get_index_snapshot()
            message  = intel.format_check_message(snapshot)
            send(chat_id, message)
        except Exception as e:
            logger.error("Check failed: %s", e)
            send(chat_id, f"❌ Market data error: {e}")

    threading.Thread(target=run, daemon=True).start()


def cmd_top5(chat_id):
    path = Path("app/data/final_ranking.csv")
    if not path.exists():
        send(chat_id, "No scan data yet. Run main.py first.")
        return

    df = pd.read_csv(path)
    top = df.head(5)

    mtime     = datetime.fromtimestamp(path.stat().st_mtime)
    scan_time = mtime.strftime("%d %b %H:%M")

    msg = f"📈 Top 5 Swing Picks (scanned {scan_time})\n\n"
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        score  = round(row.get("final_score", row.get("score", 0)), 1)
        ai     = row.get("ai_score", 0)
        ai_tag = f" | AI: {ai}/10" if ai > 0 else ""
        msg += f"{rank}. {row['symbol']}{ai_tag} (Score: {score})\n"

    msg += "\nTip: /decide swing  →  get entry/stop/target for these picks"
    send(chat_id, msg)


def cmd_intraday(chat_id):
    path = Path("app/data/intraday_watchlist.csv")
    if not path.exists():
        send(chat_id, "No intraday data yet. Run intraday_main.py first.")
        return

    df        = pd.read_csv(path)
    score_col = "final_score" if "final_score" in df.columns else "score"
    df        = df.sort_values(score_col, ascending=False)
    top       = df.head(5)

    mtime     = datetime.fromtimestamp(path.stat().st_mtime)
    scan_time = mtime.strftime("%d %b %H:%M")

    msg = f"⚡ Top 5 Intraday Picks (scanned {scan_time})\n\n"
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        breakout = "✅" if row.get("breakout", False) else "❌"
        vwap     = "✅" if row.get("above_vwap", True) else "❌"
        rs       = row.get("rs_vs_nifty", None)
        rs_tag   = f" | RS: {rs}x" if rs is not None else ""
        score    = round(row.get(score_col, 0), 1)
        msg += (
            f"{rank}. {row['symbol']} (Score: {score})\n"
            f"   Breakout: {breakout} | VWAP: {vwap}{rs_tag}\n"
        )

    msg += "\nTip: /decide intraday  →  get entry/stop/target for these picks"
    send(chat_id, msg)


def cmd_liveperf(chat_id):
    path = Path("app/data/realized_returns.csv")
    if not path.exists():
        send(chat_id,
             "No live track record yet.\n\n"
             "How to build one:\n"
             "1. Run /scan each evening\n"
             "2. Next morning: python track_returns.py\n"
             "3. After ~20 trades, come back here.")
        return

    df = pd.read_csv(path)
    if df.empty or "return_pct" not in df.columns:
        send(chat_id, "Track record file exists but has no data yet.")
        return

    total     = len(df)
    win_rate  = (df["return_pct"] > 0).mean() * 100
    avg_ret   = df["return_pct"].mean()
    best      = df["return_pct"].max()
    worst     = df["return_pct"].min()
    avg_win   = df[df["return_pct"] > 0]["return_pct"].mean() if (df["return_pct"] > 0).any() else 0
    avg_loss  = df[df["return_pct"] < 0]["return_pct"].mean() if (df["return_pct"] < 0).any() else 0

    # Expectancy: (win_rate × avg_win) + (loss_rate × avg_loss)
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    # Date range
    first = df["pick_date"].min() if "pick_date" in df.columns else "?"
    last  = df["pick_date"].max() if "pick_date" in df.columns else "?"

    # Top 5 best picks
    top5 = df.nlargest(5, "return_pct")[["symbol", "return_pct"]]

    msg = (
        f"📈 Live Track Record\n"
        f"({first} → {last})\n\n"
        f"Trades tracked : {total}\n"
        f"Win rate       : {win_rate:.1f}%\n"
        f"Avg return     : {avg_ret:+.2f}%\n"
        f"Avg win        : {avg_win:+.2f}%\n"
        f"Avg loss       : {avg_loss:+.2f}%\n"
        f"Expectancy     : {expectancy:+.2f}%\n"
        f"Best trade     : {best:+.2f}%\n"
        f"Worst trade    : {worst:+.2f}%\n"
    )

    if total >= 20:
        health = "✅ Sample size good" if win_rate >= 55 else ("⚠️ Win rate low — review" if win_rate >= 45 else "🔴 Win rate poor — pause and review")
        msg += f"\nSystem health  : {health}\n"

    msg += "\nTop 5 picks:\n"
    for _, row in top5.iterrows():
        msg += f"  {row['symbol']}: {row['return_pct']:+.2f}%\n"

    if total < 20:
        msg += f"\n⚠️ Only {total} trades — need 20+ for reliable stats."

    send(chat_id, msg)


def cmd_performance(chat_id):
    path = Path("app/data/portfolio_backtest.csv")
    if not path.exists():
        send(chat_id, "No backtest data. Run portfolio_backtest.py first.")
        return

    df         = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])

    capital = 100_000.0
    equity  = []
    for r in df["portfolio_return"]:
        capital *= (1 + r / 100)
        equity.append(capital)

    df["equity"]  = equity
    total_return  = (capital / 100_000 - 1) * 100
    years         = (df["date"].max() - df["date"].min()).days / 365.25
    cagr          = ((capital / 100_000) ** (1 / years) - 1) * 100 if years > 0 else 0
    rolling_max   = df["equity"].cummax()
    drawdown      = ((df["equity"] - rolling_max) / rolling_max) * 100
    max_dd        = drawdown.min()
    win_rate      = (df["portfolio_return"] > 0).mean() * 100
    mean_r        = df["portfolio_return"].mean()
    std_r         = df["portfolio_return"].std()
    sharpe        = (mean_r - 6.5 / 52) / std_r * math.sqrt(52) if std_r > 0 else 0

    msg = (
        f"📊 Backtest Performance\n"
        f"({df['date'].min().date()} → {df['date'].max().date()})\n\n"
        f"Rebalances  : {len(df)}\n"
        f"Total Return: {total_return:.1f}%\n"
        f"CAGR        : {cagr:.1f}%\n"
        f"Sharpe      : {sharpe:.2f}\n"
        f"Max Drawdown: {max_dd:.1f}%\n"
        f"Win Rate    : {win_rate:.1f}%\n"
        f"Avg Return  : {mean_r:.2f}% / period"
    )
    send(chat_id, msg)


def cmd_status(chat_id):
    market = MarketFilter()
    regime, top_n, vix_str = market.get_regime()

    regime_display = {
        "BEAR":             "🔴 BEAR — scans paused",
        "BULL_EXTREME_VIX": f"🔴 BULL but VIX={vix_str} (extreme fear) — top {top_n} only",
        "BULL_HIGH_VIX":    f"⚠️  BULL, VIX={vix_str} (elevated) — top {top_n}",
        "BULL_LOW_VIX":     f"✅ BULL, VIX={vix_str} (low fear) — full scan, top {top_n}",
    }

    swing_path = Path("app/data/final_ranking.csv")
    swing_time = (
        datetime.fromtimestamp(swing_path.stat().st_mtime).strftime("%d %b %H:%M")
        if swing_path.exists() else "never"
    )

    intra_path = Path("app/data/intraday_watchlist.csv")
    intra_time = (
        datetime.fromtimestamp(intra_path.stat().st_mtime).strftime("%d %b %H:%M")
        if intra_path.exists() else "never"
    )

    msg = (
        f"📡 Momentum Hunter Status\n\n"
        f"Regime: {regime_display.get(regime, regime)}\n\n"
        f"Last swing scan   : {swing_time}\n"
        f"Last intraday scan: {intra_time}\n\n"
        f"Type /decide for today's actionable recommendation."
    )
    send(chat_id, msg)


def cmd_add(chat_id, args=""):
    """
    /add SYMBOL ENTRY
    /add SYMBOL ENTRY STOP TARGET   ← custom levels
    Examples:
      /add RELIANCE 2450
      /add RELIANCE 2450 2425 2499
    """
    global _pos_chat_id
    parts = args.strip().upper().split()

    if len(parts) < 2:
        send(chat_id, "Usage: /add SYMBOL ENTRY\nExample: /add RELIANCE 2450\n\nOr with custom levels:\n/add RELIANCE 2450 2425 2499")
        return

    symbol = parts[0]
    try:
        entry = float(parts[1])
    except ValueError:
        send(chat_id, "Entry price must be a number. Example: /add RELIANCE 2450")
        return

    if len(parts) >= 4:
        try:
            stop   = float(parts[2])
            target = float(parts[3])
        except ValueError:
            send(chat_id, "Stop/target must be numbers. Example: /add RELIANCE 2450 2425 2499")
            return
    else:
        stop   = round(entry * (1 - DECISION_INTRADAY_STOP_PCT   / 100), 2)
        target = round(entry * (1 + DECISION_INTRADAY_TARGET_PCT / 100), 2)

    with _pos_lock:
        _positions[symbol] = {
            "entry":          entry,
            "stop":           stop,
            "target":         target,
            "added_at":       datetime.now(),
            "alerted_stop":   False,
            "alerted_target": False,
        }
    _pos_chat_id = chat_id

    send(chat_id,
         f"✅ Tracking {symbol}\n"
         f"Entry  ₹{entry}\n"
         f"Stop   ₹{stop}  ({DECISION_INTRADAY_STOP_PCT}% below)\n"
         f"Target ₹{target}  ({DECISION_INTRADAY_TARGET_PCT}% above)\n\n"
         f"Alerts: stop hit · target hit · 3:00 PM · 3:15 PM")


def cmd_positions(chat_id):
    with _pos_lock:
        if not _positions:
            send(chat_id, "No open positions.\nAdd one: /add SYMBOL ENTRY_PRICE")
            return
        snapshot = dict(_positions)

    quotes = get_angel_one().get_ltp_bulk(list(snapshot.keys()))

    lines = [f"📊 Open Positions — {datetime.now().strftime('%H:%M')}", ""]
    total_pnl = []

    for sym, pos in snapshot.items():
        price = quotes.get(sym.upper())

        if price:
            pnl   = round(((price - pos["entry"]) / pos["entry"]) * 100, 2)
            arrow = "📈" if pnl >= 0 else "📉"
            total_pnl.append(pnl)
            price_line = f"Now ₹{price} ({pnl:+.2f}%) {arrow}"
        else:
            price_line = "price unavailable"

        lines.append(
            f"{sym}\n"
            f"  Entry ₹{pos['entry']} | {price_line}\n"
            f"  Stop  ₹{pos['stop']}  | Target ₹{pos['target']}"
        )

    if total_pnl:
        avg = round(sum(total_pnl) / len(total_pnl), 2)
        lines.append(f"\nAvg P&L: {avg:+.2f}%")

    lines.append("\n/exit SYMBOL  or  /exit all")
    send(chat_id, "\n".join(lines))


def cmd_exit(chat_id, args=""):
    args = args.strip().upper()

    with _pos_lock:
        if not _positions:
            send(chat_id, "No open positions to exit.")
            return

        if args == "ALL":
            count = len(_positions)
            _positions.clear()
            send(chat_id, f"✅ Cleared all {count} position(s).")
            return

        if not args:
            syms = ", ".join(_positions.keys())
            send(chat_id, f"Specify a symbol or 'all'.\nOpen: {syms}\nExample: /exit RELIANCE")
            return

        if args in _positions:
            pos = _positions.pop(args)
            send(chat_id, f"✅ {args} removed (entry was ₹{pos['entry']}).")
        else:
            syms = ", ".join(_positions.keys())
            send(chat_id, f"'{args}' not found.\nOpen positions: {syms}")


def cmd_scan(chat_id, args=""):
    """
    Trigger a scan from Telegram.
      /scan                 → swing full scan   (~5 min)
      /scan intraday        → intraday full scan (~5 min, all 347 stocks)
      /scan intraday fast   → intraday fast scan (~30-45s, top 20 swing picks)
    The scan scripts send their own Telegram results when done.
    """
    parts     = args.strip().lower().split()
    fast_mode = "fast" in parts
    mode      = "intraday" if "intraday" in parts else "swing"
    label     = ("Intraday fast" if fast_mode else "Intraday") if mode == "intraday" else "Swing"
    eta       = "~30-45s" if fast_mode else "~5 min"

    if _scan_running[mode]:
        send(chat_id, f"⏳ {label} scan already running. Wait for it to finish.")
        return

    send(chat_id, f"⏳ Starting {label} scan ({eta})...\nPicks will be sent automatically when done.")

    cmd = [sys.executable, "intraday_main.py"] if mode == "intraday" else [sys.executable, "main.py"]
    if fast_mode:
        cmd.append("--fast")

    csv_path = Path("app/data/intraday_watchlist.csv" if mode == "intraday" else "app/data/final_ranking.csv")
    decide_cmd = f"/decide {mode}" if mode == "intraday" else "/decide swing"

    def run():
        _scan_running[mode] = True
        try:
            # No capture_output — subprocess writes directly to terminal so you can watch progress
            result = subprocess.run(cmd, timeout=600)

            if result.returncode != 0:
                send(chat_id, f"❌ {label} scan failed (exit {result.returncode}). Check the terminal for details.")
                return

            # exit 0 can mean "completed" OR "skipped due to BEAR regime"
            # Distinguish by checking if the CSV was updated in the last 2 minutes
            if csv_path.exists() and (time.time() - csv_path.stat().st_mtime) < 120:
                send(chat_id, f"✅ {label} scan complete. Run {decide_cmd} for entry/stop/target.")
            else:
                send(chat_id,
                     f"⚠️ Scan ran in BEAR defensive mode but found no qualifying stocks.\n"
                     f"Healthcare/IT/FMCG picks may all be below their own 200 DMA too.\n"
                     f"Use /status to check regime. Capital preserved.")

        except subprocess.TimeoutExpired:
            send(chat_id, f"❌ {label} scan timed out (>10 min). Check the terminal.")
        except Exception as e:
            logger.error("Scan subprocess error: %s", e)
            send(chat_id, f"❌ {label} scan error: {e}")
        finally:
            _scan_running[mode] = False

    threading.Thread(target=run, daemon=True).start()


def cmd_about(chat_id):
    # ── Message 1: Overview + workflow ───────────────────────────────
    send(chat_id,
        "🤖 Momentum Hunter\n"
        "AI-powered NSE scanner → Gemini analysis → actionable trades\n\n"

        "━━━━━━ HOW IT WORKS ━━━━━━\n"
        "1. SCAN scores 347 Nifty500 stocks on:\n"
        "   • 1M/3M/6M momentum returns\n"
        "   • 200 DMA trend filter\n"
        "   • Volume + breakout signals\n"
        "   • Gemini AI conviction (1–10)\n"
        "   • Sector cap (max 2 per sector)\n\n"
        "2. DECIDE combines live market + picks\n"
        "   + Gemini → gives you:\n"
        "   • Trade yes/no with reasoning\n"
        "   • Top 3 stocks: entry/stop/target\n"
        "   • Position size % adjusted for VIX\n\n"
        "3. AUTO-PROTECTION:\n"
        "   • NIFTY below 200DMA → scan paused\n"
        "   • VIX > 25 → skip / minimal size\n"
        "   • VIX > 20 → reduced positions\n\n"

        "━━━━━━ DAILY WORKFLOW ━━━━━━\n"
        "Evening:  /scan\n"
        "9:00 AM:  /scan intraday fast\n"
        "9:20 AM:  /decide swing\n"
        "          /decide intraday\n"
        "          /add SYMBOL ENTRY  (track positions)\n"
        "Midday:   /scan intraday fast (optional)\n"
        "3:00 PM:  Bot reminds you to exit\n"
        "3:20 PM:  Hard deadline — exit all intraday\n\n"
        "Run /decide between 9:15–3:30 PM\n"
        "for live NSE prices."
    )

    # ── Message 2: All commands ───────────────────────────────────────
    send(chat_id,
        "━━━━━━ SCAN COMMANDS ━━━━━━\n"
        "/scan                — Swing full scan (~5 min)\n"
        "/scan intraday       — Intraday full scan (~5 min)\n"
        "/scan intraday fast  — Fast scan, top picks (~30s)\n\n"

        "━━━━━━ DECISION COMMANDS ━━━━━━\n"
        "/decide              — AI decision: swing + intraday\n"
        "/decide swing        — Swing only\n"
        "/decide intraday     — Intraday only\n"
        "/check               — Live NIFTY/VIX/sectors\n\n"

        "━━━━━━ POSITION TRACKER ━━━━━━\n"
        "/add SYMBOL PRICE    — Track intraday position\n"
        "/add SYM ENTRY SL TG — Track with custom levels\n"
        "/positions           — Live P&L for open trades\n"
        "/exit SYMBOL         — Remove from tracking\n"
        "/exit all            — Clear all positions\n"
        "Auto alerts: stop hit · target hit\n"
        "             3:00 PM · 3:15 PM reminders\n\n"

        "━━━━━━ DATA COMMANDS ━━━━━━\n"
        "/top5        — Latest swing picks\n"
        "/intraday    — Latest intraday picks\n"
        "/status      — Market regime + VIX\n"
        "/performance — Historical backtest stats\n"
        "/liveperf    — Your actual live track record\n"
        "/about       — This guide\n"
        "/help        — Commands list"
    )

    # ── Message 3: Kite execution guide ──────────────────────────────
    send(chat_id,
        "━━━━━━ KITE EXECUTION GUIDE ━━━━━━\n"
        "Bot output: Entry ₹X  Stop ₹Y  Target ₹Z\n\n"

        "STEP 1 — BUY (after market opens 9:20 AM)\n"
        "  Product : MIS\n"
        "  Type    : LIMIT\n"
        "  Price   : X  (entry from bot)\n\n"

        "STEP 2 — SELL stop (place immediately after fill)\n"
        "  Product : MIS\n"
        "  Type    : SL-M\n"
        "  Trigger : Y  (stop from bot)\n\n"

        "STEP 3 — SELL target\n"
        "  Product : MIS\n"
        "  Type    : LIMIT\n"
        "  Price   : Z  (target from bot)\n\n"

        "⚠️ Once stop OR target fills, cancel the other order immediately.\n\n"

        "QTY FORMULA:\n"
        "  (Capital × size%) ÷ entry price\n"
        "  e.g. ₹5L × 3% ÷ ₹2450 = 6 shares\n\n"

        "EASIER — BRACKET ORDER (BO):\n"
        "  One order handles all 3 legs.\n"
        "  Type    : BO\n"
        "  Price   : X\n"
        "  Stop    : X − Y  (points below entry)\n"
        "  Target  : Z − X  (points above entry)\n"
        "  Kite auto-cancels the other leg.\n\n"

        "PRODUCT TYPES:\n"
        "  MIS  = Intraday (auto-exits 3:20 PM)\n"
        "  CNC  = Delivery (do NOT use for intraday)\n\n"

        "ORDER TYPES:\n"
        "  LIMIT  = fills only at your price or better\n"
        "  SL-M   = triggers at price, fills at market\n"
        "  BO     = bracket: entry + stop + target in one\n\n"

        "Hard rule: exit all MIS by 3:20 PM.\n"
        "Bot alerts you at 3:00 and 3:15 PM."
    )


def cmd_help(chat_id):
    msg = (
        "🤖 Momentum Hunter Bot\n\n"
        "━━━━━━ SCAN COMMANDS ━━━━━━━━━━\n"
        "/scan                 — Swing scan (~5 min)\n"
        "/scan intraday        — Intraday full scan (~5 min)\n"
        "/scan intraday fast   — Intraday fast scan (~30s)\n\n"
        "━━━━━━ DECISION COMMANDS ━━━━━━\n"
        "/decide          — AI picks entry/stop/target\n"
        "/decide swing    — Swing trades only\n"
        "/decide intraday — Intraday trades only\n"
        "/check           — Live NIFTY, VIX, sectors\n\n"
        "━━━━━━ POSITION TRACKER ━━━━━━━\n"
        "/add SYMBOL PRICE — track intraday position\n"
        "/positions        — live P&L for open trades\n"
        "/exit SYMBOL      — remove from tracking\n"
        "/exit all         — clear all positions\n\n"
        "━━━━━━ DATA COMMANDS ━━━━━━━━━━\n"
        "/top5            — Latest swing picks\n"
        "/intraday        — Latest intraday picks\n"
        "/status          — Market regime + VIX\n"
        "/performance     — Historical backtest stats\n"
        "/liveperf        — Your actual live track record\n"
        "/about           — Full guide + workflow\n"
        "/help            — This message\n\n"
        "Workflow: /scan → /decide → /add → watch alerts"
    )
    send(chat_id, msg)


COMMANDS = {
    "/scan":        cmd_scan,
    "/decide":      cmd_decide,
    "/check":       cmd_check,
    "/add":         cmd_add,
    "/positions":   cmd_positions,
    "/exit":        cmd_exit,
    "/top5":        cmd_top5,
    "/intraday":    cmd_intraday,
    "/performance": cmd_performance,
    "/liveperf":    cmd_liveperf,
    "/status":      cmd_status,
    "/about":       cmd_about,
    "/help":        cmd_help,
}

# Commands that accept an optional argument after the command word
_TAKES_ARGS = {"/scan", "/decide", "/add", "/exit"}


# ==========================================
# BOT LOOP
# ==========================================

def run():
    logger.info("Momentum Hunter Bot is running.")
    logger.info("Send /help in Telegram to see available commands.")

    threading.Thread(target=_position_monitor, daemon=True, name="pos-monitor").start()
    logger.info("Position monitor started (checks every 60s during market hours).")

    offset = None

    while True:
        try:
            data = get_updates(offset)

            for update in data.get("result", []):
                offset  = update["update_id"] + 1
                message = update.get("message", {})
                text    = message.get("text", "").strip()
                chat_id = message.get("chat", {}).get("id")

                if not text or not chat_id:
                    continue

                # Strip bot username suffix (e.g. /top5@MyBot → /top5)
                parts   = text.split("@")[0].split(None, 1)
                command = parts[0].lower()
                args    = parts[1] if len(parts) > 1 else ""

                logger.info("Command: %s %s (chat %s)", command, args, chat_id)

                handler = COMMANDS.get(command)
                if handler:
                    if command in _TAKES_ARGS:
                        handler(chat_id, args)
                    else:
                        handler(chat_id)
                else:
                    send(chat_id, "Unknown command. Type /help for the list.")

        except KeyboardInterrupt:
            logger.info("Bot stopped.")
            break

        except Exception as e:
            logger.error("Bot loop error: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    run()
