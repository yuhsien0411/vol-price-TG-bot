import logging
import requests
from config import TG_TOKEN, TG_CHAT_ID

logger = logging.getLogger(__name__)


def send_message(text: str) -> bool:
    """透過 Telegram Bot API 發送純文字訊息。"""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("TG 發送失敗: %s", exc)
        return False
