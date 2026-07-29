from fastapi import APIRouter, HTTPException

from app.db import is_db_configured, load_latest_swing_ranking, load_latest_intraday_watchlist
from api.schemas import (
    SwingRankingResponse, SwingPick,
    IntradayWatchlistResponse, IntradayPick,
)

router = APIRouter(prefix="/api")


def _require_db():
    if not is_db_configured():
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured on this deployment")


@router.get("/swing/latest", response_model=SwingRankingResponse)
def get_latest_swing_ranking():
    _require_db()
    df = load_latest_swing_ranking()
    if df.empty:
        return SwingRankingResponse(picks=[])

    scan_time = df["scan_time"].iloc[0]
    regime = df["regime"].iloc[0]
    vix = df["vix"].iloc[0]

    picks = [
        SwingPick(symbol=r.symbol, score=r.score, ai_score=r.ai_score, final_score=r.final_score)
        for r in df.itertuples()
    ]
    return SwingRankingResponse(scan_time=scan_time, regime=regime, vix=vix, picks=picks)


@router.get("/intraday/latest", response_model=IntradayWatchlistResponse)
def get_latest_intraday_watchlist():
    _require_db()
    df = load_latest_intraday_watchlist()
    if df.empty:
        return IntradayWatchlistResponse(picks=[])

    scan_time = df["scan_time"].iloc[0]

    picks = [
        IntradayPick(
            symbol=r.symbol, score=r.score, volume_ratio=r.volume_ratio,
            return_pct=r.return_pct, breakout=r.breakout, above_vwap=r.above_vwap,
            vwap=r.vwap, rs_vs_nifty=r.rs_vs_nifty, last_close=r.last_close,
            ai_score=r.ai_score, final_score=r.final_score,
        )
        for r in df.itertuples()
    ]
    return IntradayWatchlistResponse(scan_time=scan_time, picks=picks)
