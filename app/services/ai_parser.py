import json
from app.logger import get_logger

logger = get_logger(__name__)

# highest_risk is only present in swing prompts, not intraday — treat as optional
_REQUIRED_KEYS = {"stocks", "highest_conviction", "avoid", "market_sentiment"}
_CONVICTION_MIN = 1.0
_CONVICTION_MAX = 10.0


class AIParser:

    def parse(self, response):
        if not response:
            logger.error("Empty response from Gemini")
            return None

        # Strip markdown code fences Gemini sometimes wraps JSON in
        cleaned = response.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            snippet = cleaned[:300].replace("\n", " ")
            logger.error("JSON decode failed: %s", e)
            logger.debug("Response snippet: %s", snippet)
            return None

        # Check all required top-level keys are present
        missing = _REQUIRED_KEYS - set(data.keys())
        if missing:
            logger.error("Missing keys in AI response: %s", missing)
            return None

        # Validate stocks list
        stocks = data.get("stocks")
        if not isinstance(stocks, list) or not stocks:
            logger.error("'stocks' must be a non-empty list")
            return None

        sanitized = []
        for entry in stocks:
            if not isinstance(entry, dict) or "symbol" not in entry or "conviction" not in entry:
                logger.warning("Malformed stock entry skipped: %s", entry)
                continue
            try:
                conviction = float(entry["conviction"])
            except (TypeError, ValueError):
                logger.warning("Non-numeric conviction for %s, skipping", entry.get("symbol"))
                continue
            # Clamp conviction to valid range
            entry["conviction"] = max(_CONVICTION_MIN, min(_CONVICTION_MAX, conviction))
            sanitized.append(entry)

        if not sanitized:
            logger.error("No valid stock entries after sanitization")
            return None

        data["stocks"] = sanitized
        return data
