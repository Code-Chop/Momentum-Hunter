"""
DecisionService — asks Gemini to make a fully actionable trading decision
given live index data, the latest scan picks, and current stock prices.

Output is a structured dict with picks, entry/stop/target levels,
position size, and reasoning. Designed to minimise daily decisions
for the trader — one /decide query returns everything needed to act.
"""
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.logger import get_logger
from app.services.market_intelligence import MarketIntelligence
from app.services.gemini_service import GeminiService
from config import (
    GEMINI_API_KEY,
    ATR_SWING_STOP_MULT, ATR_SWING_TARGET_MULT,
    ATR_INTRADAY_STOP_MULT, ATR_INTRADAY_TARGET_MULT,
    DECISION_SWING_STOP_PCT, DECISION_SWING_TARGET_PCT,
    DECISION_INTRADAY_STOP_PCT, DECISION_INTRADAY_TARGET_PCT,
)

logger = get_logger(__name__)

_SWING_CSV    = Path("app/data/final_ranking.csv")
_INTRADAY_CSV = Path("app/data/intraday_watchlist.csv")

_CACHE_TTL = 1800   # reuse last Gemini decision for 30 minutes
_cache: dict = {}   # {mode: {"ts": float, "decision": dict}}


class DecisionService:

    def __init__(self):
        self.intelligence = MarketIntelligence()
        self.gemini       = GeminiService(GEMINI_API_KEY)
        self._atrs: dict  = {}   # {symbol: atr_value} populated in _format_prices

    # ── Public API ────────────────────────────────────────────────────

    def get_decision(self, mode: str = "both") -> dict | None:
        """
        mode: "swing" | "intraday" | "both"
        Returns a structured decision dict, or None on failure.
        Caches the Gemini response for 30 minutes to preserve API quota.
        """
        # ── Return cached result if fresh enough ──────────────────────
        cached = _cache.get(mode)
        if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
            age_min = int((time.time() - cached["ts"]) / 60)
            logger.info("Returning cached decision for mode=%s (age: %dm)", mode, age_min)
            return cached["decision"]

        logger.info("Building decision for mode=%s", mode)

        snapshot   = self.intelligence.get_index_snapshot()
        market_ctx = self.intelligence.format_for_prompt(snapshot)

        picks_ctx, candidate_symbols = self._load_picks(mode)

        prices = {}
        if candidate_symbols:
            logger.info("Fetching live prices for %d candidates...", len(candidate_symbols))
            prices = self.intelligence.get_stock_prices(candidate_symbols)

        prices_ctx = self._format_prices(prices, mode)

        prompt = self._build_prompt(market_ctx, picks_ctx, prices_ctx, mode)
        logger.debug("Decision prompt size: %d chars", len(prompt))

        raw = self.gemini.analyze(prompt)
        logger.debug("Raw decision response:\n%s", raw)

        decision = self._parse(raw)
        if decision:
            decision = self._attach_levels(decision, prices, mode)
            _cache[mode] = {"ts": time.time(), "decision": decision}

        return decision

    # ── Data loading ──────────────────────────────────────────────────

    def _load_picks(self, mode: str) -> tuple[str, list[str]]:
        sections = []
        symbols  = []

        if mode in ("swing", "both") and _SWING_CSV.exists():
            df      = pd.read_csv(_SWING_CSV)
            score_c = "final_score" if "final_score" in df.columns else "score"
            df      = df.sort_values(score_c, ascending=False).head(10)
            mtime   = datetime.fromtimestamp(_SWING_CSV.stat().st_mtime).strftime("%d %b %H:%M")
            lines   = [f"Swing picks (last scan {mtime}):"]
            for _, r in df.iterrows():
                lines.append(
                    f"  {r['symbol']}: score={round(r.get(score_c, 0), 1)}"
                    + (f", AI={r['ai_score']}/10" if r.get("ai_score", 0) > 0 else "")
                )
                symbols.append(r["symbol"])
            sections.append("\n".join(lines))

        if mode in ("intraday", "both") and _INTRADAY_CSV.exists():
            df      = pd.read_csv(_INTRADAY_CSV)
            score_c = "final_score" if "final_score" in df.columns else "score"
            df      = df.sort_values(score_c, ascending=False).head(10)
            mtime   = datetime.fromtimestamp(_INTRADAY_CSV.stat().st_mtime).strftime("%d %b %H:%M")
            lines   = [f"Intraday picks (last scan {mtime}):"]
            for _, r in df.iterrows():
                breakout = "✅" if r.get("breakout") else "❌"
                vwap     = "✅" if r.get("above_vwap") else "❌"
                lines.append(
                    f"  {r['symbol']}: score={round(r.get(score_c, 0), 1)}"
                    f", breakout={breakout}, vwap={vwap}"
                    f", vol={r.get('volume_ratio', 'N/A')}x"
                )
                symbols.append(r["symbol"])
            sections.append("\n".join(lines))

        if not sections:
            return "No scan data available — run main.py or intraday_main.py first.", []

        return "\n\n".join(sections), list(dict.fromkeys(symbols))  # dedup, preserve order

    def _format_prices(self, prices: dict, mode: str) -> str:
        """
        Build price context for the Gemini prompt.
        Stops and targets use ATR(14) so they scale with each stock's actual volatility
        rather than a flat percentage. Falls back to fixed % if ATR is unavailable.
        """
        if not prices:
            return "Current prices: unavailable"

        self._atrs = {}
        lines = ["Current stock prices with ATR-based levels (real-time NSE):"]

        for sym, px in prices.items():
            atr = self.intelligence.get_stock_atr(sym)
            self._atrs[sym] = atr

            if atr:
                stop_s = round(px - ATR_SWING_STOP_MULT   * atr, 2)
                tgt_s  = round(px + ATR_SWING_TARGET_MULT * atr, 2)
                stop_i = round(px - ATR_INTRADAY_STOP_MULT   * atr, 2)
                tgt_i  = round(px + ATR_INTRADAY_TARGET_MULT * atr, 2)
                atr_note = f" | ATR14=Rs{round(atr, 1)}"
            else:
                stop_s = round(px * (1 - DECISION_SWING_STOP_PCT    / 100), 2)
                tgt_s  = round(px * (1 + DECISION_SWING_TARGET_PCT  / 100), 2)
                stop_i = round(px * (1 - DECISION_INTRADAY_STOP_PCT  / 100), 2)
                tgt_i  = round(px * (1 + DECISION_INTRADAY_TARGET_PCT / 100), 2)
                atr_note = ""

            lines.append(
                f"  {sym}: Rs{px}{atr_note}"
                f" | swing stop Rs{stop_s} / target Rs{tgt_s}"
                f" | intraday stop Rs{stop_i} / target Rs{tgt_i}"
            )
        return "\n".join(lines)

    # ── Prompt ────────────────────────────────────────────────────────

    def _build_prompt(self, market_ctx, picks_ctx, prices_ctx, mode):
        mode_instruction = {
            "swing":    "Focus on swing trading (multi-day holds).",
            "intraday": "Focus on intraday trading (same-day exits).",
            "both":     "Decide whether swing, intraday, or both are appropriate right now.",
        }.get(mode, "")

        return f"""You are an expert NSE trading advisor helping a retail trader minimise daily decisions.
{mode_instruction}

{market_ctx}

{picks_ctx}

{prices_ctx}

Based on ALL the above data, return ONE trading decision in this exact JSON format:

{{
  "should_trade": true,
  "trade_type": "swing",
  "confidence": 8,
  "position_size_pct": 3,
  "top_picks": [
    {{"symbol": "RELIANCE", "entry": 2450.0, "stop": 2401.0, "target": 2572.0}},
    {{"symbol": "HDFCBANK", "entry": 1685.0, "stop": 1651.3, "target": 1769.3}}
  ],
  "avoid": ["COALINDIA"],
  "reasoning": "2-3 sentence explanation of the market and why these picks",
  "key_risk": "single most important risk to watch today",
  "entry_window": "9:20-10:00 AM"
}}

Rules:
- should_trade: ALWAYS true — the trader wants picks regardless of market regime
- trade_type: "swing" | "intraday" | "both"
- confidence: 1-10 (lower in bearish conditions, that is fine)
- position_size_pct: 1-2 if NIFTY below 200 DMA or VIX elevated, up to 5 in strong bull
- top_picks: max 3 symbols with entry/stop/target from the price data above
- entry/stop/target: use the pre-calculated levels from the real-time price data, adjusting slightly based on context
- reasoning: include a bear market disclaimer if NIFTY is below 200 DMA
- avoid: symbols to skip despite good scores
- entry_window: best time window to enter (IST)
- output ONLY valid JSON, no markdown
"""

    # ── Response parsing ──────────────────────────────────────────────

    def _parse(self, raw: str) -> dict | None:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(cleaned)
        except Exception as e:
            logger.error("Decision parse failed: %s | snippet: %s", e, cleaned[:200])
            return None

        required = {"should_trade", "trade_type", "confidence", "top_picks", "reasoning"}
        if not required.issubset(data.keys()):
            logger.error("Decision missing keys: %s", required - set(data.keys()))
            return None

        return data

    def _attach_levels(self, decision: dict, prices: dict, mode: str) -> dict:
        """
        Fallback: fill in entry/stop/target for any pick where Gemini omitted
        or gave obviously wrong values. Uses ATR-based levels when available.
        """
        is_intraday  = mode == "intraday"
        stop_mult    = ATR_INTRADAY_STOP_MULT    if is_intraday else ATR_SWING_STOP_MULT
        target_mult  = ATR_INTRADAY_TARGET_MULT  if is_intraday else ATR_SWING_TARGET_MULT
        stop_pct_fb  = DECISION_INTRADAY_STOP_PCT   if is_intraday else DECISION_SWING_STOP_PCT
        target_pct_fb = DECISION_INTRADAY_TARGET_PCT if is_intraday else DECISION_SWING_TARGET_PCT

        for pick in decision.get("top_picks", []):
            sym = pick.get("symbol", "")
            px  = prices.get(sym)
            if px is None:
                continue

            if not pick.get("entry") or abs(pick["entry"] - px) / px > 0.05:
                pick["entry"] = px

            atr = self._atrs.get(sym)
            if atr:
                default_stop   = round(pick["entry"] - stop_mult   * atr, 2)
                default_target = round(pick["entry"] + target_mult * atr, 2)
            else:
                default_stop   = round(pick["entry"] * (1 - stop_pct_fb   / 100), 2)
                default_target = round(pick["entry"] * (1 + target_pct_fb / 100), 2)

            if not pick.get("stop") or pick["stop"] >= pick["entry"]:
                pick["stop"] = default_stop
            if not pick.get("target") or pick["target"] <= pick["entry"]:
                pick["target"] = default_target

        return decision

    # ── Telegram message formatter ────────────────────────────────────

    @staticmethod
    def format_message(decision: dict, snapshot: dict) -> str:
        if not decision:
            return "❌ Could not generate a decision. Try again in a few minutes."

        now = datetime.now().strftime("%d %b %H:%M")

        # Header
        nifty = snapshot.get("NIFTY50", {})
        vix   = snapshot.get("VIX", {})
        nifty_line = (
            f"NIFTY {nifty.get('current', 'N/A'):,}"
            f" ({nifty.get('change_pct', 0):+.2f}%)"
            + (" ✅" if nifty.get("above_ma200") else " ⚠️")
        ) if nifty else "NIFTY: N/A"
        vix_line = (
            f"VIX {vix.get('current', 'N/A')} ({vix.get('change_pct', 0):+.2f}%) "
            f"{'↓' if vix.get('trend') == 'falling' else '↑'}"
        ) if vix else "VIX: N/A"

        # Trade verdict
        trade   = decision.get("should_trade", False)
        t_type  = decision.get("trade_type", "none").upper()
        conf    = decision.get("confidence", "?")
        size    = decision.get("position_size_pct", "?")
        verdict = f"✅ TRADE — {t_type}" if trade else "🚫 SKIP TRADING TODAY"
        conf_line = f"Confidence: {conf}/10 | Size: {size}% per trade"

        lines = [
            f"🧠 AI Decision — {now}",
            "",
            f"📊 {nifty_line}",
            f"   {vix_line}",
            "",
            verdict,
            conf_line,
        ]

        # Picks
        picks = decision.get("top_picks", [])
        if picks and trade:
            lines.append("\n📈 Take These Positions:")
            for i, p in enumerate(picks, 1):
                sym    = p.get("symbol", "?")
                entry  = p.get("entry", "?")
                stop   = p.get("stop", "?")
                target = p.get("target", "?")
                lines.append(
                    f"  {i}. {sym}\n"
                    f"     Entry Rs{entry}  Stop Rs{stop}  Target Rs{target}"
                )

        # Avoid
        avoid = decision.get("avoid", [])
        if avoid:
            lines.append(f"\n🚫 Skip: {', '.join(avoid)}")

        # Reasoning + risk
        reasoning = decision.get("reasoning", "")
        key_risk  = decision.get("key_risk", "")
        window    = decision.get("entry_window", "")

        if reasoning:
            lines.append(f"\n💡 {reasoning}")
        if key_risk:
            lines.append(f"⚠️ Risk: {key_risk}")
        if window and trade:
            lines.append(f"⏰ Enter: {window}")

        lines.append("\n⚠️ Prices are real-time NSE. Still verify before placing orders.")

        return "\n".join(lines)
