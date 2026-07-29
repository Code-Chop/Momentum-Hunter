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
from config import DATABASE_URL, CHAT_ACCESS_TOKEN

logger = get_logger("chat_commands")

_scan_running = {"swing": False, "intraday": False}


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
    try:
        intel = MarketIntelligence()
        snapshot = intel.get_index_snapshot()
        return intel.format_check_message(snapshot)
    except Exception as e:
        logger.error("Check failed: %s", e)
        return f"❌ Market data error: {e}"


def cmd_scan(args: str) -> str:
    parts = args.strip().lower().split()
    fast_mode = "fast" in parts
    mode = "intraday" if "intraday" in parts else "swing"
    label = ("Intraday fast" if fast_mode else "Intraday") if mode == "intraday" else "Swing"
    eta = "~30-45s" if fast_mode else "~5 min"

    if _scan_running[mode]:
        return f"⏳ {label} scan already running. Wait for it to finish."

    cmd = [sys.executable, "intraday_main.py"] if mode == "intraday" else [sys.executable, "main.py"]
    if fast_mode:
        cmd.append("--fast")

    csv_path = Path("app/data/intraday_watchlist.csv" if mode == "intraday" else "app/data/final_ranking.csv")

    def run():
        from app.db import save_chat_message
        _scan_running[mode] = True
        try:
            result = subprocess.run(cmd, timeout=600)
            if result.returncode != 0:
                save_chat_message("assistant", f"❌ {label} scan failed (exit {result.returncode}).")
                return
            if csv_path.exists() and (time.time() - csv_path.stat().st_mtime) < 120:
                save_chat_message("assistant", f"✅ {label} scan complete. Try /top5 or /intraday.")
            else:
                save_chat_message(
                    "assistant",
                    f"⚠️ {label} scan ran but found no qualifying stocks (defensive/BEAR mode?). "
                    f"Use /status to check regime.",
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


def cmd_help() -> str:
    return (
        "Commands:\n"
        "/top5 — top 5 swing picks from the last scan\n"
        "/intraday — top 5 intraday picks from the last scan\n"
        "/status — market regime, VIX, last scan times\n"
        "/check — instant market pulse (no AI, ~5s)\n"
        "/scan — run a swing scan (~5 min)\n"
        "/scan intraday [fast] — run an intraday scan\n"
        "/help — this list"
    )


def dispatch(message: str, token: str | None = None) -> str:
    text = message.strip()
    lower = text.lower()

    if lower.startswith("/top5"):
        return cmd_top5()
    if lower.startswith("/intraday"):
        return cmd_intraday()
    if lower.startswith("/status"):
        return cmd_status()
    if lower.startswith("/check"):
        return cmd_check()
    if lower.startswith("/scan"):
        if CHAT_ACCESS_TOKEN and token != CHAT_ACCESS_TOKEN:
            return "🔒 /scan requires an access code on this deployment. Ask the owner for it."
        return cmd_scan(text[len("/scan"):])
    if lower.startswith("/help") or lower.startswith("/start"):
        return cmd_help()

    return "Unrecognized command. Type /help to see what's available."
