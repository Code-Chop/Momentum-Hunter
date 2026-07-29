import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import pandas as pd
from app.logger import get_logger
from app.services.ai_report_service import AIReportService
from app.services.performance_tracker import PerformanceTracker
from app.services.downloader import StockDownloader
from app.services.momentum import MomentumCalculator
from app.services.telegram_service import TelegramService
from app.services.market_filter import MarketFilter
from config import BOT_TOKEN, CHAT_ID, AI_CONVICTION_WEIGHT_SWING, DATABASE_URL

logger = get_logger("swing_scan_service")


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
            "\n===== SECTOR DISTRIBUTION (%d picks) =====\n%s",
            n,
            result[["symbol", "sector", "final_score"]].to_string(index=False),
        )
    return result


def run_swing_scan() -> pd.DataFrame:
    """Run the daily swing scan: momentum score → Gemini conviction → diversified
    picks → persist (CSV best-effort + Postgres when configured) → Telegram alert.

    Returns the full final ranking DataFrame (symbol, score, ai_score, final_score).
    """
    # ── MARKET REGIME GATE ──────────────────────────────────────────────
    market = MarketFilter()
    regime, top_n, vix_str = market.get_regime()

    bear_mode = (regime == "BEAR")
    if bear_mode:
        top_n = 10  # scan full universe, disclaimer added to message

    regime_msg = {
        "BEAR":             "BEAR market (NIFTY below 200 DMA) — scanning all stocks, disclaimer will be sent.",
        "BULL_EXTREME_VIX": f"VIX={vix_str} (extreme fear). Cautious — top {top_n} only.",
        "BULL_HIGH_VIX":    f"VIX={vix_str} (elevated fear). Cautious — top {top_n} only.",
        "BULL_LOW_VIX":     f"BULL market, VIX={vix_str} (low fear). Full scan — top {top_n}.",
    }
    logger.info(regime_msg.get(regime, f"Regime: {regime}"))

    # ── INITIALIZE SERVICES ─────────────────────────────────────────────
    downloader = StockDownloader()
    calculator = MomentumCalculator()
    ai_service = AIReportService()
    tracker = PerformanceTracker()
    telegram = TelegramService(BOT_TOKEN, CHAT_ID)

    # ── LOAD STOCKS ──────────────────────────────────────────────────────
    stocks_df = pd.read_csv("app/data/stocks.csv")
    has_sector = "sector" in stocks_df.columns
    stocks = stocks_df["symbol"].tolist()
    logger.info("Loaded %d stocks from universe", len(stocks))

    # ── SCAN STOCKS ──────────────────────────────────────────────────────
    results = []
    for stock in stocks:
        try:
            logger.debug("Scanning %s...", stock)
            data = downloader.get_stock_data(stock)
            score = calculator.calculate_score(data)
            if score is not None:
                results.append({"symbol": stock, "score": score})
        except Exception as e:
            logger.error("Error scanning %s: %s", stock, e)

    results.sort(key=lambda x: x["score"], reverse=True)
    ranking_df = pd.DataFrame(results)

    logger.info("Scan complete: %d stocks scored", len(ranking_df))
    logger.info("\n===== MOMENTUM RANKINGS =====\n%s", ranking_df.head(20).to_string(index=False))

    try:
        ranking_df.to_csv("app/data/watchlist.csv", index=False)
    except OSError as e:
        logger.warning("Could not write watchlist.csv (ephemeral FS?): %s", e)

    # ── AI REPORT ────────────────────────────────────────────────────────
    logger.info("Generating AI report...")
    ai_report = ai_service.generate_report(ranking_df, regime=regime, vix=vix_str)

    if ai_report:
        logger.info("\n===== AI REPORT =====\n%s", ai_report)

    # ── MERGE AI SCORES ──────────────────────────────────────────────────
    if ai_report:
        ai_scores = {s["symbol"]: s["conviction"] for s in ai_report["stocks"]}
        ranking_df["ai_score"] = ranking_df["symbol"].map(ai_scores).fillna(0)
        ranking_df["final_score"] = (
            ranking_df["score"] + ranking_df["ai_score"] * AI_CONVICTION_WEIGHT_SWING
        )
        ranking_df = ranking_df.sort_values("final_score", ascending=False)
    else:
        logger.warning("AI report unavailable — falling back to momentum-only ranking")
        ranking_df["ai_score"] = 0
        ranking_df["final_score"] = ranking_df["score"]

    logger.info(
        "\n===== FINAL AI RANKING =====\n%s",
        ranking_df[["symbol", "score", "ai_score", "final_score"]].head(20).to_string(index=False)
    )

    # ── SECTOR DIVERSIFICATION CAP ───────────────────────────────────────
    top_stocks = get_diversified_picks(ranking_df, stocks_df, n=top_n, has_sector=has_sector)

    # ── SAVE + TRACK ─────────────────────────────────────────────────────
    try:
        ranking_df.to_csv("app/data/final_ranking.csv", index=False)
        logger.info("Final ranking saved to app/data/final_ranking.csv")
    except OSError as e:
        logger.warning("Could not write final_ranking.csv (ephemeral FS?): %s", e)

    tracker.save_daily_picks(top_stocks)

    if DATABASE_URL:
        from app.db import save_swing_ranking
        try:
            save_swing_ranking(ranking_df, regime=regime, vix=vix_str)
            logger.info("Swing ranking persisted to Postgres")
        except Exception as e:
            logger.error("Failed to persist swing ranking to Postgres: %s", e)

    # ── TELEGRAM MESSAGE ─────────────────────────────────────────────────
    regime_tag = {
        "BULL_LOW_VIX":     "📈",
        "BULL_HIGH_VIX":    "⚠️",
        "BULL_EXTREME_VIX": "🔴",
        "BEAR":             "⚠️",
    }.get(regime, "📈")

    if bear_mode:
        message = (
            f"⚠️ BEAR MARKET — NIFTY below 200 DMA [VIX={vix_str}]\n"
            f"Broad market is in a downtrend. Trade at your own risk.\n"
            f"Keep position size to 1% max. Consider paper trading first.\n\n"
        )
    else:
        message = f"{regime_tag} Momentum Hunter Picks [VIX={vix_str}]\n\n"

    for rank, (_, row) in enumerate(top_stocks.iterrows(), start=1):
        message += f"{rank}. {row['symbol']} (Score: {round(row['final_score'], 1)})\n"

    if ai_report:
        message += (
            f"\n🏆 Highest Conviction: {ai_report['highest_conviction']}"
            f"\n⚠️ Highest Risk: {ai_report.get('highest_risk', 'N/A')}"
            f"\n🚫 Avoid: {ai_report['avoid']}"
            f"\n📊 Sentiment: {ai_report['market_sentiment']}"
        )

    response = telegram.send_message(message)
    logger.info("Telegram response: %s", response)
    logger.info("Done.")

    return ranking_df
