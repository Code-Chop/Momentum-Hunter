import math

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


def _num(value, default=0.0):
    """JSON has no NaN/Infinity literal, so a non-finite float in the database
    fails serialization and 500s the whole endpoint. Degrade the one value
    instead of losing the response."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _opt_num(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


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
        SwingPick(
            symbol=r.symbol,
            score=_num(r.score),
            ai_score=_num(r.ai_score),
            final_score=_num(r.final_score),
        )
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
            symbol=r.symbol, score=_num(r.score), volume_ratio=_num(r.volume_ratio),
            return_pct=_num(r.return_pct), breakout=bool(r.breakout), above_vwap=bool(r.above_vwap),
            vwap=_num(r.vwap), rs_vs_nifty=_opt_num(r.rs_vs_nifty), last_close=_num(r.last_close),
            ai_score=_num(r.ai_score), final_score=_num(r.final_score),
        )
        for r in df.itertuples()
    ]
    return IntradayWatchlistResponse(scan_time=scan_time, picks=picks)
