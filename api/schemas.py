from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SwingPick(BaseModel):
    symbol: str
    score: float
    ai_score: float
    final_score: float


class SwingRankingResponse(BaseModel):
    scan_time: Optional[datetime] = None
    regime: Optional[str] = None
    vix: Optional[str] = None
    picks: list[SwingPick]


class IntradayPick(BaseModel):
    symbol: str
    score: float
    volume_ratio: float
    return_pct: float
    breakout: bool
    above_vwap: bool
    vwap: float
    rs_vs_nifty: Optional[float] = None
    last_close: float
    ai_score: float
    final_score: float


class IntradayWatchlistResponse(BaseModel):
    scan_time: Optional[datetime] = None
    picks: list[IntradayPick]
