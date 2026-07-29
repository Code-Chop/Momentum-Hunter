import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_NIFTY_FILTER = os.getenv("USE_NIFTY_FILTER", "True") == "True"

# ── Hosting / Cloud ─────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # "owner/repo", for workflow_dispatch

# ── Market Regime ──────────────────────────────────────────────────────
VIX_HIGH = 20.0        # elevated fear → top 7 only
VIX_EXTREME = 25.0     # extreme fear  → top 5 only

# ── Bear Market Defensive Scan ─────────────────────────────────────────
BEAR_DEFENSIVE_SECTORS = [
    "Healthcare",
    "Fast Moving Consumer Goods",
    "Information Technology",
]
BEAR_DEFENSIVE_TOP_N = 3

# ── Momentum Score Weights ─────────────────────────────────────────────
MOMENTUM_WEIGHT_1M = 0.40
MOMENTUM_WEIGHT_3M = 0.30
MOMENTUM_WEIGHT_6M = 0.20
MOMENTUM_WEIGHT_VOL = 0.10

# ── Momentum Score Adjustments ─────────────────────────────────────────
MOMENTUM_50DMA_PENALTY = 20      # below 50 DMA → short-term weakness
MOMENTUM_200DMA_PENALTY = 30     # below 200 DMA → long-term downtrend (was hardcoded)
MOMENTUM_VOL_BASELINE = 25.0     # target annualized volatility %
MOMENTUM_VOL_QUALITY_MIN = 0.6
MOMENTUM_VOL_QUALITY_MAX = 1.4
MOMENTUM_VOL_CAP = 2.5           # cap volume ratio (reduced from 3.0 — more conservative)
MOMENTUM_VOL_BASELINE_DAYS = 63  # rolling window for volume baseline (one quarter)
MOMENTUM_52W_NEAR_BONUS = 15     # within 5% of 52w high
MOMENTUM_52W_FAR_BONUS = 7       # within 10% of 52w high
MOMENTUM_52W_NEAR_PCT = 95
MOMENTUM_52W_FAR_PCT = 90
MOMENTUM_RSI_LOW = 40
MOMENTUM_RSI_SWEET_LOW = 50
MOMENTUM_RSI_SWEET_HIGH = 70
MOMENTUM_RSI_HIGH = 75
MOMENTUM_RSI_SWEET_BONUS = 5
MOMENTUM_RSI_OVERBOUGHT_PENALTY = 10
MOMENTUM_RSI_WEAK_PENALTY = 10

# ── AI Conviction Weighting ────────────────────────────────────────────
AI_CONVICTION_WEIGHT_SWING = 3
AI_CONVICTION_WEIGHT_INTRADAY = 2

# ── Intraday Scanner — normalized 0-100 signal weights ────────────────
# Normal market: return momentum leads, RS confirms
INTRADAY_W_VOL    = 0.20
INTRADAY_W_RET    = 0.30
INTRADAY_W_RET5   = 0.20
INTRADAY_W_RS     = 0.15
INTRADAY_W_VWAP   = 0.10
INTRADAY_W_BREAK  = 0.05

# Bear market: RS (alpha vs Nifty) becomes primary signal
INTRADAY_W_VOL_BEAR   = 0.15
INTRADAY_W_RET_BEAR   = 0.10
INTRADAY_W_RET5_BEAR  = 0.10
INTRADAY_W_RS_BEAR    = 0.45
INTRADAY_W_VWAP_BEAR  = 0.10
INTRADAY_W_BREAK_BEAR = 0.10

# Normalization caps — signals are divided by these to reach ±1 scale
INTRADAY_RET_CAP   = 3.0   # ±3% for last-bar return
INTRADAY_RET5_CAP  = 5.0   # ±5% for 25-min return
INTRADAY_RS_CAP    = 3.0   # ±3% alpha cap
INTRADAY_VOL_NORM  = 2.0   # 2x average volume = full strength (1.0)

# Legacy constants kept for backward compat with any remaining references
INTRADAY_VOLUME_WEIGHT = 2
INTRADAY_RETURN_WEIGHT = 10
INTRADAY_RETURN5_WEIGHT = 5
INTRADAY_RS_WEIGHT = 5
INTRADAY_BREAKOUT_BONUS = 20
INTRADAY_BELOW_VWAP_PENALTY = 15
INTRADAY_RETURN_WEIGHT_BEAR = 5
INTRADAY_RS_WEIGHT_BEAR = 15

# ── ATR multipliers for stops and targets ─────────────────────────────
ATR_SWING_STOP_MULT   = 2.0   # stop  = entry − 2 × ATR(14)
ATR_SWING_TARGET_MULT = 3.0   # target = entry + 3 × ATR(14)  → R:R 1.5
ATR_INTRADAY_STOP_MULT   = 1.5
ATR_INTRADAY_TARGET_MULT = 2.0  # R:R ~1.3

# Fallback fixed % if ATR unavailable
DECISION_SWING_STOP_PCT      = 2.0
DECISION_SWING_TARGET_PCT    = 5.0
DECISION_INTRADAY_STOP_PCT   = 1.0
DECISION_INTRADAY_TARGET_PCT = 2.0

# ── Live Index Symbols ────────────────────────────────────────────────
INDEX_NIFTY     = "^NSEI"
INDEX_BANKNIFTY = "^NSEBANK"
INDEX_VIX       = "^INDIAVIX"
INDEX_IT        = "^CNXIT"
INDEX_AUTO      = "^CNXAUTO"
INDEX_PHARMA    = "^CNXPHARMA"

# ── Angel One SmartAPI ────────────────────────────────────────────────
ANGEL_API_KEY     = os.getenv("ANGEL_API_KEY", "")
ANGEL_CLIENT_ID   = os.getenv("ANGEL_CLIENT_ID", "")
ANGEL_PASSWORD    = os.getenv("ANGEL_PASSWORD", "")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "")

# ── Download Retry Settings ────────────────────────────────────────────
DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 2.0
