import logging
import json
import aiohttp
from config import TG_TOKEN, TG_CHAT_ID

logger = logging.getLogger(__name__)


async def send_message(session: aiohttp.ClientSession, text: str) -> bool:
    """透過 Telegram Bot API 非同步發送純文字訊息。"""
    if not TG_TOKEN or not TG_CHAT_ID:
        logger.warning("TG_TOKEN 或 TG_CHAT_ID 未設定，略過發送")
        return False

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.post(url, json=payload, timeout=timeout) as resp:
            body = await resp.text()

        if resp.status >= 400:
            logger.error("TG 發送失敗: status=%s body=%s", resp.status, body)
            return False

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            logger.error("TG 發送失敗: 回應非 JSON，body=%s", body)
            return False

        if not data.get("ok", False):
            logger.error("TG 發送失敗: %s", data.get("description", "未知錯誤"))
            return False

        return True
    except Exception as exc:
        logger.error("TG 發送失敗: %s", exc)
        return False
