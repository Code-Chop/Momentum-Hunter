import re
import time
from google import genai
from app.logger import get_logger

logger = get_logger(__name__)

_MODEL          = "gemini-2.5-flash-lite"
_MAX_RETRIES    = 4
_RETRY_DELAY    = 5.0    # base delay for general errors
_OVERLOAD_DELAY = 15.0   # base delay for 503 overload — needs longer gaps


def _parse_retry_after(exc) -> float | None:
    """Extract retry delay from a 429 error message if present."""
    try:
        match = re.search(r"retry.*?(\d+(?:\.\d+)?)\s*s", str(exc), re.IGNORECASE)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None


class GeminiService:

    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    def analyze(self, prompt: str) -> str:
        last_exc = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=_MODEL,
                    contents=prompt,
                )
                return response.text

            except Exception as e:
                last_exc = e
                err_str = str(e)
                is_quota = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                is_overload = "503" in err_str or "UNAVAILABLE" in err_str

                if attempt < _MAX_RETRIES:
                    if is_quota:
                        # Respect the retry-after hint from the API
                        wait = _parse_retry_after(e) or (_RETRY_DELAY * attempt)
                        logger.warning(
                            "Gemini quota hit (attempt %d/%d) — waiting %.0fs before retry",
                            attempt, _MAX_RETRIES, wait,
                        )
                        time.sleep(wait)
                    elif is_overload:
                        wait = _OVERLOAD_DELAY * attempt
                        logger.warning(
                            "Gemini overloaded (attempt %d/%d) — waiting %.0fs",
                            attempt, _MAX_RETRIES, wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.warning("Gemini attempt %d/%d failed: %s", attempt, _MAX_RETRIES, e)
                        time.sleep(_RETRY_DELAY)

        logger.error("Gemini API failed after %d attempts: %s", _MAX_RETRIES, last_exc)
        raise last_exc
