import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
import pandas as pd
from datetime import datetime, timezone, timedelta, time as dtime

from app.logger import get_logger
from app.services.downloader import StockDownloader
from app.services.telegram_service import TelegramService
from app.services.intraday_scanner import IntradayScanner
from app.services.news_service import NewsService
from app.services.report_builder import ReportBuilder
from app.services.gemini_service import GeminiService
from app.services.ai_parser import AIParser
from app.services.market_filter import MarketFilter
from config import BOT_TOKEN, CHAT_ID, GEMINI_API_KEY, AI_CONVICTION_WEIGHT_INTRADAY, DATABASE_URL

logger = get_logger("intraday_scan_service")

_IST = timedelta(hours=5, minutes=30)


def _is_market_hours() -> bool:
    now_ist = (datetime.now(timezone.utc) + _IST).time()
    return dtime(9, 15) <= now_ist <= dtime(15, 30)


def get_diversified_picks(df, stocks_sector_df, n, max_per_sector=2, has_sector=True):
    """Select top n stocks while capping concentration per sector."""
    if not has_sector:
        return df.head(n)

    merged = df.merge(
        stocks_sector_df[["symbol", "sector"]],
        on="symbol",
        how="left",
    )
    merged["sector"] = merged["sector"].fillna("Unknown")

    selected = []
    sector_counts = {}

    for _, row in merged.iterrows():
        sector = row["sector"]
        if sector_counts.get(sector, 0) < max_per_sector:
            selected.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= n:
            break

    result = pd.DataFrame(selected)
    if "sector" in result.columns:
        logger.info(
            "\n===== SECTOR DISTRIBUTION (intraday %d picks) =====\n%s",
            n,
            result[["symbol", "sector", "final_score"]].to_string(index=False),
        )
    return result


def _load_prior_top20(has_db: bool):
    """Load the previous run's top-20 symbols by final_score, DB-first with CSV fallback."""
    if has_db:
        from app.db import load_latest_intraday_watchlist
        try:
            prior_df = load_latest_intraday_watchlist()
            if not prior_df.empty:
                score_col = "final_score" if "final_score" in prior_df.columns else "score"
                return prior_df.sort_values(score_col, ascending=False).head(20)["symbol"].tolist()
        except Exception as e:
            logger.warning("Could not load prior intraday watchlist from Postgres: %s", e)

    csv_path = Path("app/data/intraday_watchlist.csv")
    if csv_path.exists():
        prior_df = pd.read_csv(csv_path)
        score_col = "final_score" if "final_score" in prior_df.columns else "score"
        return prior_df.sort_values(score_col, ascending=False).head(20)["symbol"].tolist()

    return None


def run_intraday_scan(fast_mode: bool = False) -> pd.DataFrame:
    """Run the intraday scan: 15-min bar scoring → Gemini conviction (top 20) →
    diversified top 5 → persist (CSV best-effort + Postgres when configured) →
    Telegram alert → paper trade log during market hours.

    Returns the full intraday ranking DataFrame.
    """
    has_db = bool(DATABASE_URL)

    downloader = StockDownloader()
    scanner = IntradayScanner()
    telegram = TelegramService(BOT_TOKEN, CHAT_ID)
    news_service = NewsService()
    report_builder = ReportBuilder()
    gemini = GeminiService(GEMINI_API_KEY)
    ai_parser = AIParser()

    # ── MARKET REGIME (for AI prompt context) ───────────────────────────
    regime, _, vix_str = MarketFilter().get_regime()
    logger.info("Market regime: %s | VIX: %s", regime, vix_str)

    # ── LOAD STOCKS ──────────────────────────────────────────────────────
    stocks_df = pd.read_csv("app/data/stocks.csv")
    has_sector = "sector" in stocks_df.columns

    if fast_mode:
        prior_top20 = _load_prior_top20(has_db)
        if prior_top20:
            stocks = prior_top20
            logger.info("Fast mode: scanning top %d from last intraday results", len(stocks))
        else:
            logger.warning("Fast mode requested but no prior intraday results found — falling back to full scan")
            stocks = stocks_df["symbol"].tolist()
            logger.info("Loaded %d stocks from universe", len(stocks))
    else:
        stocks = stocks_df["symbol"].tolist()
        logger.info("Loaded %d stocks from universe", len(stocks))

    # ── NIFTY INTRADAY RETURN (for RS calculation) ──────────────────────
    nifty_return = 0.0
    try:
        nifty_df = downloader.get_index_intraday_data("^NSEI")
        if not nifty_df.empty:
            last_ts = nifty_df.index[-1]
            today_start = last_ts.normalize()
            today_nifty = nifty_df[nifty_df.index >= today_start]
            if len(today_nifty) >= 2:
                first_close = float(today_nifty["Close"].iloc[0])
                last_close = float(today_nifty["Close"].iloc[-1])
                nifty_return = ((last_close - first_close) / first_close) * 100
                logger.info("NIFTY intraday return: %.2f%%", nifty_return)
    except Exception as e:
        logger.error("NIFTY fetch failed: %s", e)

    # ── SCAN ALL STOCKS ──────────────────────────────────────────────────
    results = []
    logger.info("Running intraday scan...")

    for stock in stocks:
        try:
            df = downloader.get_intraday_data(stock)
            scan_result = scanner.calculate_score(df, nifty_return=nifty_return, regime=regime)
            if scan_result is not None:
                results.append({
                    "symbol": stock,
                    "score": scan_result["score"],
                    "volume_ratio": scan_result["volume_ratio"],
                    "return_pct": scan_result["return_pct"],
                    "breakout": scan_result["breakout"],
                    "above_vwap": scan_result["above_vwap"],
                    "vwap": scan_result["vwap"],
                    "rs_vs_nifty": scan_result["rs_vs_nifty"],
                    "last_close": float(df["Close"].iloc[-1]),
                })
        except Exception as e:
            logger.error("%s: %s", stock, e)

    logger.info("Scan complete: %d stocks scored", len(results))

    ranking_df = pd.DataFrame(results)

    if ranking_df.empty:
        logger.warning("No stocks scored — exiting.")
        return ranking_df

    ranking_df = ranking_df.sort_values(by="score", ascending=False)

    logger.info(
        "\n===== INTRADAY TOP 20 =====\n%s",
        ranking_df.head(20).to_string(index=False)
    )

    # ── AI LAYER — TOP 20 → NEWS → GEMINI ────────────────────────────────
    top_20 = ranking_df.head(20)
    logger.info("Fetching news for top 20...")

    news_data = {}
    for _, row in top_20.iterrows():
        symbol = row["symbol"]
        news_data[symbol] = news_service.get_news(symbol)
        logger.debug("%s: %d headlines", symbol, len(news_data[symbol]))

    logger.info("Running Gemini intraday analysis...")

    ai_report = None
    try:
        prompt = report_builder.build_intraday_prompt(top_20, news_data, regime=regime, vix=vix_str)
        logger.info("Prompt size: %d characters", len(prompt))
        response = gemini.analyze(prompt)
        logger.debug("Raw Gemini response:\n%s", response)
        ai_report = ai_parser.parse(response)
    except Exception as e:
        logger.error("AI analysis failed: %s", e)

    # ── MERGE AI SCORES + FINAL RANKING ──────────────────────────────────
    if ai_report:
        ai_scores = {s["symbol"]: s["conviction"] for s in ai_report["stocks"]}
        ranking_df["ai_score"] = ranking_df["symbol"].map(ai_scores).fillna(0)
        ranking_df["final_score"] = (
            ranking_df["score"] + ranking_df["ai_score"] * AI_CONVICTION_WEIGHT_INTRADAY
        )
        ranking_df = ranking_df.sort_values("final_score", ascending=False)
        logger.info(
            "\n===== FINAL AI-RANKED INTRADAY TOP 20 =====\n%s",
            ranking_df[
                ["symbol", "score", "ai_score", "final_score",
                 "volume_ratio", "return_pct", "breakout", "above_vwap"]
            ].head(20).to_string(index=False)
        )
    else:
        ranking_df["ai_score"] = 0
        ranking_df["final_score"] = ranking_df["score"]
        logger.warning("AI step skipped — using raw intraday scores.")

    # ── SECTOR DIVERSIFICATION CAP (top 5) ───────────────────────────────
    top_stocks = get_diversified_picks(ranking_df, stocks_df, n=5, has_sector=has_sector)

    # ── TELEGRAM ALERT ────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_label = "⚡ INTRADAY FAST SCAN" if fast_mode else "⚡ INTRADAY AI PICKS"
    message = f"{scan_label} — {timestamp[:10]}\n\n"

    for rank, (_, row) in enumerate(top_stocks.iterrows(), start=1):
        breakout_icon = "✅" if row["breakout"] else "❌"
        vwap_icon = "✅" if row["above_vwap"] else "❌"
        rs_text = f"α{row['rs_vs_nifty']:+.2f}%" if row["rs_vs_nifty"] is not None else "N/A"
        ai_text = f" | AI: {row['ai_score']}/10" if row["ai_score"] > 0 else ""

        message += (
            f"{rank}. {row['symbol']}{ai_text}\n"
            f"Score: {row['final_score']:.1f} | "
            f"Vol: {row['volume_ratio']}x | "
            f"Ret: {row['return_pct']}%\n"
            f"Breakout: {breakout_icon} | "
            f"VWAP: {vwap_icon} | "
            f"RS: {rs_text}\n\n"
        )

    if ai_report:
        message += (
            f"🏆 Top Pick: {ai_report.get('highest_conviction', 'N/A')}\n"
            f"🚫 Avoid: {ai_report.get('avoid', 'N/A')}\n"
            f"📊 Sentiment: {ai_report.get('market_sentiment', 'N/A')}"
        )

    response = telegram.send_message(message)
    logger.info("Telegram response: %s", response)

    # ── SAVE PAPER TRADES ─────────────────────────────────────────────────
    if _is_market_hours():
        paper_trades = []
        for _, row in top_stocks.iterrows():
            paper_trades.append({
                "timestamp": timestamp,
                "symbol": row["symbol"],
                "entry_price": row["last_close"],
                "score": row["score"],
                "ai_score": row["ai_score"],
                "final_score": row["final_score"],
                "volume_ratio": row["volume_ratio"],
                "return_pct": row["return_pct"],
                "breakout": row["breakout"],
                "above_vwap": row["above_vwap"],
            })

        paper_df = pd.DataFrame(paper_trades)
        file_path = "app/data/paper_trades.csv"
        try:
            paper_df.to_csv(
                file_path,
                mode="a",
                header=(not os.path.exists(file_path)),
                index=False,
            )
        except OSError as e:
            logger.warning("Could not write paper_trades.csv (ephemeral FS?): %s", e)
    else:
        logger.info("Outside market hours (09:15–15:30 IST) — skipping paper trade log.")

    # ── SAVE FULL WATCHLIST ───────────────────────────────────────────────
    try:
        ranking_df.to_csv("app/data/intraday_watchlist.csv", index=False)
        logger.info("Saved: app/data/intraday_watchlist.csv")
    except OSError as e:
        logger.warning("Could not write intraday_watchlist.csv (ephemeral FS?): %s", e)

    if has_db:
        from app.db import save_intraday_watchlist
        try:
            save_intraday_watchlist(ranking_df, fast_mode=fast_mode)
            logger.info("Intraday watchlist persisted to Postgres")
        except Exception as e:
            logger.error("Failed to persist intraday watchlist to Postgres: %s", e)

    return ranking_df
