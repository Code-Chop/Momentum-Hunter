"""Postgres persistence layer (Supabase-hosted) for scan results.

Used when DATABASE_URL is configured (GitHub Actions / Render deployments).
Local/dev usage without DATABASE_URL falls back to the existing CSV files —
callers should check is_db_configured() before using this module.
"""
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, Date,
    UniqueConstraint, func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import DATABASE_URL

Base = declarative_base()

_engine = None
_SessionLocal = None


def is_db_configured() -> bool:
    return bool(DATABASE_URL)


def _normalize_url(url: str) -> str:
    """Force the psycopg3 driver regardless of the scheme Supabase/Render hand us."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def get_engine():
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")
        _engine = create_engine(_normalize_url(DATABASE_URL), poolclass=NullPool, pool_pre_ping=True)
    return _engine


def _session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


class SwingRanking(Base):
    __tablename__ = "swing_ranking"
    id = Column(Integer, primary_key=True)
    scan_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    regime = Column(String)
    vix = Column(String)
    symbol = Column(String, nullable=False)
    score = Column(Float)
    ai_score = Column(Float)
    final_score = Column(Float)


class IntradayWatchlist(Base):
    __tablename__ = "intraday_watchlist"
    id = Column(Integer, primary_key=True)
    scan_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    fast_mode = Column(Boolean, default=False)
    symbol = Column(String, nullable=False)
    score = Column(Float)
    volume_ratio = Column(Float)
    return_pct = Column(Float)
    breakout = Column(Boolean)
    above_vwap = Column(Boolean)
    vwap = Column(Float)
    rs_vs_nifty = Column(Float)
    last_close = Column(Float)
    ai_score = Column(Float)
    final_score = Column(Float)


class PerformanceLog(Base):
    __tablename__ = "performance_log"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    symbol = Column(String, nullable=False)
    momentum_score = Column(Float)
    ai_score = Column(Float)
    final_score = Column(Float)
    __table_args__ = (UniqueConstraint("date", "symbol", name="uq_performance_log_date_symbol"),)


class TrackedPosition(Base):
    __tablename__ = "tracked_position"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False)
    entry = Column(Float)
    stop = Column(Float)
    target = Column(Float)
    chat_id = Column(String)
    alerted_stop = Column(Boolean, default=False)
    alerted_target = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_message"
    id = Column(Integer, primary_key=True)
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def create_all_tables():
    Base.metadata.create_all(get_engine())


# ---------------------------------------------------------------------------
# Swing ranking
# ---------------------------------------------------------------------------

def save_swing_ranking(ranking_df: pd.DataFrame, regime: str = None, vix: str = None):
    scan_time = datetime.utcnow()
    session = _session()
    try:
        for _, row in ranking_df.iterrows():
            session.add(SwingRanking(
                scan_time=scan_time,
                regime=regime,
                vix=vix,
                symbol=row["symbol"],
                score=float(row.get("score", 0) or 0),
                ai_score=float(row.get("ai_score", 0) or 0),
                final_score=float(row.get("final_score", 0) or 0),
            ))
        session.commit()
    finally:
        session.close()


def load_latest_swing_ranking() -> pd.DataFrame:
    session = _session()
    try:
        latest_time = session.query(func.max(SwingRanking.scan_time)).scalar()
        if latest_time is None:
            return pd.DataFrame(columns=["symbol", "score", "ai_score", "final_score"])
        rows = (
            session.query(SwingRanking)
            .filter(SwingRanking.scan_time == latest_time)
            .order_by(SwingRanking.final_score.desc())
            .all()
        )
        return pd.DataFrame([{
            "symbol": r.symbol, "score": r.score, "ai_score": r.ai_score,
            "final_score": r.final_score, "scan_time": r.scan_time,
            "regime": r.regime, "vix": r.vix,
        } for r in rows])
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Intraday watchlist
# ---------------------------------------------------------------------------

def save_intraday_watchlist(ranking_df: pd.DataFrame, fast_mode: bool = False):
    scan_time = datetime.utcnow()
    session = _session()
    try:
        for _, row in ranking_df.iterrows():
            session.add(IntradayWatchlist(
                scan_time=scan_time,
                fast_mode=fast_mode,
                symbol=row["symbol"],
                score=float(row.get("score", 0) or 0),
                volume_ratio=float(row.get("volume_ratio", 0) or 0),
                return_pct=float(row.get("return_pct", 0) or 0),
                breakout=bool(row.get("breakout", False)),
                above_vwap=bool(row.get("above_vwap", False)),
                vwap=float(row.get("vwap", 0) or 0),
                rs_vs_nifty=float(row["rs_vs_nifty"]) if row.get("rs_vs_nifty") is not None else None,
                last_close=float(row.get("last_close", 0) or 0),
                ai_score=float(row.get("ai_score", 0) or 0),
                final_score=float(row.get("final_score", 0) or 0),
            ))
        session.commit()
    finally:
        session.close()


def load_latest_intraday_watchlist() -> pd.DataFrame:
    session = _session()
    try:
        latest_time = session.query(func.max(IntradayWatchlist.scan_time)).scalar()
        if latest_time is None:
            return pd.DataFrame(columns=["symbol", "score", "final_score"])
        rows = (
            session.query(IntradayWatchlist)
            .filter(IntradayWatchlist.scan_time == latest_time)
            .order_by(IntradayWatchlist.final_score.desc())
            .all()
        )
        return pd.DataFrame([{
            "symbol": r.symbol, "score": r.score, "volume_ratio": r.volume_ratio,
            "return_pct": r.return_pct, "breakout": r.breakout, "above_vwap": r.above_vwap,
            "vwap": r.vwap, "rs_vs_nifty": r.rs_vs_nifty, "last_close": r.last_close,
            "ai_score": r.ai_score, "final_score": r.final_score, "scan_time": r.scan_time,
        } for r in rows])
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Performance log
# ---------------------------------------------------------------------------

def upsert_performance_log(df: pd.DataFrame):
    if df.empty:
        return
    engine = get_engine()
    records = df.to_dict(orient="records")
    with engine.begin() as conn:
        stmt = pg_insert(PerformanceLog.__table__).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "symbol"],
            set_={
                "momentum_score": stmt.excluded.momentum_score,
                "ai_score": stmt.excluded.ai_score,
                "final_score": stmt.excluded.final_score,
            },
        )
        conn.execute(stmt)


# ---------------------------------------------------------------------------
# Tracked positions (stop/target monitor)
# ---------------------------------------------------------------------------

def add_tracked_position(symbol: str, entry: float, stop: float, target: float, chat_id: str):
    session = _session()
    try:
        session.add(TrackedPosition(
            symbol=symbol, entry=entry, stop=stop, target=target, chat_id=chat_id,
        ))
        session.commit()
    finally:
        session.close()


def list_tracked_positions(chat_id: str = None) -> pd.DataFrame:
    session = _session()
    try:
        query = session.query(TrackedPosition)
        if chat_id is not None:
            query = query.filter(TrackedPosition.chat_id == chat_id)
        rows = query.order_by(TrackedPosition.added_at.desc()).all()
        return pd.DataFrame([{
            "id": r.id, "symbol": r.symbol, "entry": r.entry, "stop": r.stop,
            "target": r.target, "chat_id": r.chat_id,
            "alerted_stop": r.alerted_stop, "alerted_target": r.alerted_target,
            "added_at": r.added_at,
        } for r in rows])
    finally:
        session.close()


def remove_tracked_position(position_id: int):
    session = _session()
    try:
        session.query(TrackedPosition).filter(TrackedPosition.id == position_id).delete()
        session.commit()
    finally:
        session.close()


def mark_position_alerted(position_id: int, stop: bool = False, target: bool = False):
    session = _session()
    try:
        pos = session.query(TrackedPosition).filter(TrackedPosition.id == position_id).first()
        if pos:
            if stop:
                pos.alerted_stop = True
            if target:
                pos.alerted_target = True
            session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Chat history (web dashboard command chat)
# ---------------------------------------------------------------------------

def save_chat_message(role: str, content: str):
    session = _session()
    try:
        session.add(ChatMessage(role=role, content=content))
        session.commit()
    finally:
        session.close()


def load_chat_history(limit: int = 100) -> pd.DataFrame:
    session = _session()
    try:
        rows = (
            session.query(ChatMessage)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return pd.DataFrame([{
            "id": r.id, "role": r.role, "content": r.content, "created_at": r.created_at,
        } for r in rows])
    finally:
        session.close()
