import time
import requests
import xml.etree.ElementTree as ET
from app.logger import get_logger

logger = get_logger(__name__)

_NEWS_TIMEOUT = 8       # seconds per request
_NEWS_RETRIES = 2       # total attempts on network errors


class NewsService:

    def get_news(self, stock, limit=3):
        query = stock.replace("&", "").replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}+stock"

        last_exc = None
        for attempt in range(1, _NEWS_RETRIES + 1):
            try:
                response = requests.get(url, timeout=_NEWS_TIMEOUT)
                response.raise_for_status()
                root = ET.fromstring(response.content)
                headlines = []
                for item in root.findall(".//item")[:limit]:
                    title = item.find("title")
                    if title is not None:
                        headlines.append(title.text)
                return headlines
            except requests.RequestException as e:
                last_exc = e
                logger.warning("News fetch error for %s (attempt %d/%d): %s", stock, attempt, _NEWS_RETRIES, e)
                if attempt < _NEWS_RETRIES:
                    time.sleep(1)
            except ET.ParseError as e:
                logger.warning("News XML parse error for %s: %s", stock, e)
                return []

        logger.error("News fetch failed for %s after %d attempts: %s", stock, _NEWS_RETRIES, last_exc)
        return []
