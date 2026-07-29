"""Command dispatch shared by the web chat (api/routers/chat.py).

Mirrors telegram_bot.py's command set for informational commands, and
`/scan` for triggering the same scan scripts telegram_bot.py runs, for the
free-tier and local single-user use case where there's no separate always-on
bot process — the web dashboard's chat calls the same underlying engine.
"""
import sys
import threading
import subprocess
import time
from pathlib import Path
from datetime import datetime

import pandas as pd

from app.logger import get_logger
from app.services.market_filter import MarketFilter
from app.services.market_intelligence import MarketIntelligence
from app.services.decision_service import DecisionService
from config import DATABASE_URL, CHAT_ACCESS_TOKEN, DECISION_INTRADAY_STOP_PCT, DECISION_INTRADAY_TARGET_PCT

logger = get_logger("chat_commands")

_scan_running = {"swing": False, "intraday": False}
_scan_lock = threading.Lock()

# /check hits yfinance/Angel One on every call. Cache briefly so a hammered
# public endpoint can't get our IP rate-limited by Yahoo -- which would also
# break the scans, since they use the same data source.
_CHECK_TTL_SECONDS = 60
_check_cache: dict = {"at": 0.0, "text": None}


def _latest_swing_df() -> tuple[pd.DataFrame, str]:
    if DATABASE_URL:
        from app.db import load_latest_swing_ranking
        df = load_latest_swing_ranking()
        if not df.empty:
            scan_time = df["scan_time"].iloc[0].strftime("%d %b %H:%M")
            return df, scan_time

    path = Path("app/data/final_ranking.csv")
    if not path.exists():
        return pd.DataFrame(), "never"
    return pd.read_csv(path), datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %H:%M")


def _latest_intraday_df() -> tuple[pd.DataFrame, str]:
    if DATABASE_URL:
        from app.db import load_latest_intraday_watchlist
        df = load_latest_intraday_watchlist()
        if not df.empty:
            scan_time = df["scan_time"].iloc[0].strftime("%d %b %H:%M")
            return df, scan_time

    path = Path("app/data/intraday_watchlist.csv")
    if not path.exists():
        return pd.DataFrame(), "never"
    return pd.read_csv(path), datetime.fromtimestamp(path.stat().st_mtime).strftime("%d %b %H:%M")


def cmd_top5() -> str:
    df, scan_time = _latest_swing_df()
    if df.empty:
        return "No scan data yet. Try /scan to run one."

    score_col = "final_score" if "final_score" in df.columns else "score"
    top = df.sort_values(score_col, ascending=False).head(5)

    msg = f"📈 Top 5 Swing Picks (scanned {scan_time})\n\n"
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        score = round(row.get("final_score", row.get("score", 0)), 1)
        ai = row.get("ai_score", 0)
        ai_tag = f" | AI: {ai}/10" if ai and ai > 0 else ""
        msg += f"{rank}. {row['symbol']}{ai_tag} (Score: {score})\n"
    return msg


def cmd_intraday() -> str:
    df, scan_time = _latest_intraday_df()
    if df.empty:
        return "No intraday data yet. Try /scan intraday to run one."

    score_col = "final_score" if "final_score" in df.columns else "score"
    top = df.sort_values(score_col, ascending=False).head(5)

    msg = f"⚡ Top 5 Intraday Picks (scanned {scan_time})\n\n"
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        breakout = "✅" if row.get("breakout", False) else "❌"
        vwap = "✅" if row.get("above_vwap", True) else "❌"
        score = round(row.get(score_col, 0), 1)
        msg += f"{rank}. {row['symbol']} (Score: {score})\n   Breakout: {breakout} | VWAP: {vwap}\n"
    return msg


def cmd_status() -> str:
    regime, top_n, vix_str = MarketFilter().get_regime()
    regime_display = {
        "BEAR": "🔴 BEAR — scans paused",
        "BULL_EXTREME_VIX": f"🔴 BULL but VIX={vix_str} (extreme fear) — top {top_n} only",
        "BULL_HIGH_VIX": f"⚠️ BULL, VIX={vix_str} (elevated) — top {top_n}",
        "BULL_LOW_VIX": f"✅ BULL, VIX={vix_str} (low fear) — full scan, top {top_n}",
    }

    _, swing_time = _latest_swing_df()
    _, intra_time = _latest_intraday_df()

    return (
        f"📡 Momentum Hunter Status\n\n"
        f"Regime: {regime_display.get(regime, regime)}\n\n"
        f"Last swing scan   : {swing_time}\n"
        f"Last intraday scan: {intra_time}"
    )


def cmd_check() -> str:
    now = time.time()
    if _check_cache["text"] and (now - _check_cache["at"]) < _CHECK_TTL_SECONDS:
        return _check_cache["text"]
    try:
        intel = MarketIntelligence()
        snapshot = intel.get_index_snapshot()
        text = intel.format_check_message(snapshot)
        _check_cache.update(at=now, text=text)
        return text
    except Exception as e:
        logger.error("Check failed: %s", e)
        return f"❌ Market data error: {e}"


def cmd_scan(args: str, session_id: str = None) -> str:
    parts = args.strip().lower().split()
    fast_mode = "fast" in parts
    mode = "intraday" if "intraday" in parts else "swing"
    label = ("Intraday fast" if fast_mode else "Intraday") if mode == "intraday" else "Swing"
    eta = "~30-45s" if fast_mode else "~5 min"

    # Claim the slot under a lock *before* starting the thread -- checking here
    # but setting inside the thread would let two rapid calls both get through.
    with _scan_lock:
        if _scan_running[mode]:
            return f"⏳ {label} scan already running. Wait for it to finish."
        _scan_running[mode] = True

    cmd = [sys.executable, "intraday_main.py"] if mode == "intraday" else [sys.executable, "main.py"]
    if fast_mode:
        cmd.append("--fast")

    def _latest_scan_time():
        """Postgres is the source of truth. A CSV mtime only proves a file was
        written -- it stayed 'fresh' even when every score in it was NaN."""
        try:
            df, _ = _latest_intraday_df() if mode == "intraday" else _latest_swing_df()
            return None if df.empty or "scan_time" not in df.columns else df["scan_time"].iloc[0]
        except Exception:
            return None

    before = _latest_scan_time()

    def run():
        from app.db import save_chat_message as _save
        save_chat_message = lambda role, text: _save(role, text, session_id)
        try:
            result = subprocess.run(cmd, timeout=600, capture_output=True, text=True)
            if result.returncode != 0:
                tail = (result.stderr or result.stdout or "").strip().splitlines()
                detail = "\n".join(tail[-8:]) if tail else "(no output captured)"
                save_chat_message(
                    "assistant",
                    f"❌ {label} scan failed (exit {result.returncode}).\n\n{detail}",
                )
                return
            after = _latest_scan_time()
            if after is not None and after != before:
                save_chat_message("assistant", f"✅ {label} scan complete. Try /top5 or /intraday.")
            else:
                save_chat_message(
                    "assistant",
                    f"⚠️ {label} scan finished but stored no new results — either no stocks "
                    f"qualified (defensive/BEAR mode) or the price data came back unusable. "
                    f"The previous results are still showing. Check /status for the regime.",
                )
        except subprocess.TimeoutExpired:
            save_chat_message("assistant", f"❌ {label} scan timed out (>10 min).")
        except Exception as e:
            logger.error("Scan error: %s", e)
            save_chat_message("assistant", f"❌ {label} scan error: {e}")
        finally:
            _scan_running[mode] = False

    threading.Thread(target=run, daemon=True).start()
    return f"⏳ Starting {label} scan ({eta})... Results will appear here when done."


def cmd_decide(args: str) -> str:
    mode_map = {"swing": "swing", "intraday": "intraday"}
    mode = mode_map.get(args.strip().lower(), "both")
    try:
        svc = DecisionService()
        decision = svc.get_decision(mode=mode)
        snapshot = svc.intelligence.get_index_snapshot()
        return DecisionService.format_message(decision, snapshot)
    except Exception as e:
        logger.error("Decision failed: %s", e)
        return f"❌ Decision error: {e}"


# Positions tracked from the web chat use a fixed pseudo chat_id -- this is a
# single-user deployment, and web positions are intentionally kept separate
# from telegram_bot.py's in-memory ones (different storage, no shared state).
_WEB_CHAT_ID = "web"


def cmd_add(args: str) -> str:
    parts = args.strip().upper().split()
    if len(parts) < 2:
        return "Usage: /add SYMBOL ENTRY\nExample: /add RELIANCE 2450\n\nOr with custom levels:\n/add RELIANCE 2450 2425 2499"

    symbol = parts[0]
    try:
        entry = float(parts[1])
    except ValueError:
        return "Entry price must be a number. Example: /add RELIANCE 2450"

    if len(parts) >= 4:
        try:
            stop = float(parts[2])
            target = float(parts[3])
        except ValueError:
            return "Stop/target must be numbers. Example: /add RELIANCE 2450 2425 2499"
    else:
        stop = round(entry * (1 - DECISION_INTRADAY_STOP_PCT / 100), 2)
        target = round(entry * (1 + DECISION_INTRADAY_TARGET_PCT / 100), 2)

    from app.db import add_tracked_position
    add_tracked_position(symbol, entry, stop, target, _WEB_CHAT_ID)

    return (
        f"✅ Tracking {symbol}\n"
        f"Entry  ₹{entry}\n"
        f"Stop   ₹{stop}\n"
        f"Target ₹{target}"
    )


def cmd_positions() -> str:
    from app.db import list_tracked_positions
    from app.services.angel_one import get_angel_one

    df = list_tracked_positions(chat_id=_WEB_CHAT_ID)
    if df.empty:
        return "No open positions.\nAdd one: /add SYMBOL ENTRY_PRICE"

    quotes = get_angel_one().get_ltp_bulk(df["symbol"].tolist())

    lines = ["📊 Open Positions", ""]
    pnls = []
    for _, pos in df.iterrows():
        price = quotes.get(pos["symbol"].upper())
        if price:
            pnl = round(((price - pos["entry"]) / pos["entry"]) * 100, 2)
            pnls.append(pnl)
            price_line = f"Now ₹{price} ({pnl:+.2f}%)"
        else:
            price_line = "price unavailable"
        lines.append(f"{pos['symbol']}\n  Entry ₹{pos['entry']} | {price_line}\n  Stop ₹{pos['stop']} | Target ₹{pos['target']}")

    if pnls:
        lines.append(f"\nAvg P&L: {round(sum(pnls) / len(pnls), 2):+.2f}%")
    lines.append("\n/exit SYMBOL or /exit all")
    return "\n".join(lines)


def cmd_exit(args: str) -> str:
    from app.db import list_tracked_positions, remove_tracked_position

    arg = args.strip().upper()
    df = list_tracked_positions(chat_id=_WEB_CHAT_ID)
    if df.empty:
        return "No open positions to exit."

    if arg == "ALL":
        for pos_id in df["id"]:
            remove_tracked_position(int(pos_id))
        return f"✅ Cleared all {len(df)} position(s)."

    if not arg:
        syms = ", ".join(df["symbol"])
        return f"Specify a symbol or 'all'.\nOpen: {syms}\nExample: /exit RELIANCE"

    match = df[df["symbol"] == arg]
    if match.empty:
        syms = ", ".join(df["symbol"])
        return f"'{arg}' not found.\nOpen positions: {syms}"

    remove_tracked_position(int(match.iloc[0]["id"]))
    return f"✅ {arg} removed (entry was ₹{match.iloc[0]['entry']})."


def cmd_help() -> str:
    return (
        "Commands:\n"
        "/top5 — top 5 swing picks from the last scan\n"
        "/intraday — top 5 intraday picks from the last scan\n"
        "/status — market regime, VIX, last scan times\n"
        "/check — instant market pulse (no AI, ~5s)\n"
        "/decide [swing|intraday] — AI entry/stop/target decision (~15-20s) 🔒\n"
        "/positions — live P&L for tracked positions\n"
        "/add SYMBOL ENTRY [STOP TARGET] — track a position 🔒\n"
        "/exit SYMBOL|all — stop tracking a position 🔒\n"
        "/scan [intraday [fast]] — run a scan (~30s-5min) 🔒\n"
        "/help — this list\n"
        "\n🔒 = requires the access code on this deployment"
    )


def dispatch(message: str, token: str | None = None, session_id: str | None = None) -> str:
    text = message.strip()
    lower = text.lower()

    def _authorized() -> bool:
        return not CHAT_ACCESS_TOKEN or token == CHAT_ACCESS_TOKEN

    def _locked(cmd: str) -> str:
        return f"🔒 {cmd} requires an access code on this deployment. Ask the owner for it."

    if lower.startswith("/top5"):
        return cmd_top5()
    if lower.startswith("/intraday"):
        return cmd_intraday()
    if lower.startswith("/status"):
        return cmd_status()
    if lower.startswith("/check"):
        return cmd_check()
    if lower.startswith("/decide"):
        # Calls Gemini -- gated so strangers can't spend the API quota.
        return cmd_decide(text[len("/decide"):]) if _authorized() else _locked("/decide")
    if lower.startswith("/positions"):
        return cmd_positions()
    # Position writes are gated: these are the owner's real tracked trades,
    # and an ungated /exit all would let anyone wipe them.
    if lower.startswith("/add"):
        return cmd_add(text[len("/add"):]) if _authorized() else _locked("/add")
    if lower.startswith("/exit"):
        return cmd_exit(text[len("/exit"):]) if _authorized() else _locked("/exit")
    if lower.startswith("/scan"):
        return cmd_scan(text[len("/scan"):], session_id) if _authorized() else _locked("/scan")
    if lower.startswith("/help") or lower.startswith("/start"):
        return cmd_help()

    return "Unrecognized command. Type /help to see what's available."
