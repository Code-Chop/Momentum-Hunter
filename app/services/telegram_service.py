import requests
from app.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10  # seconds


class TelegramService:

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, message):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            response = requests.post(url, json=payload, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error("Telegram send failed: %s", e)
            return {"ok": False, "error": str(e)}
