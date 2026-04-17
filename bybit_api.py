import asyncio
import logging
import aiohttp
from config import BYBIT_BASE, CONCURRENCY, EXCLUDED_SYMBOLS

logger = logging.getLogger(__name__)


async def _safe_get_json(
    session: aiohttp.ClientSession,
    url: str,
    params: dict,
    endpoint: str,
) -> dict:
    """安全抓取 JSON，連線/解析失敗時回傳空 dict。"""
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with session.get(url, params=params, timeout=timeout) as resp:
            if resp.status >= 400:
                body = await resp.text()
                logger.warning(
                    "Bybit %s HTTP 失敗 status=%s body=%s",
                    endpoint,
                    resp.status,
                    body,
                )
                return {}
            data = await resp.json()
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Bybit %s 連線或解析失敗: %s", endpoint, exc)
        return {}


def _extract_result_list(data: dict, endpoint: str) -> list[dict]:
    """驗證 Bybit 回應格式，失敗時回傳空陣列避免中斷掃描。"""
    if not isinstance(data, dict):
        logger.warning("Bybit %s 回應格式異常：非 dict", endpoint)
        return []

    ret_code = data.get("retCode")
    ret_msg = data.get("retMsg", "")
    if ret_code != 0:
        logger.warning(
            "Bybit %s 回傳失敗 retCode=%s retMsg=%s",
            endpoint,
            ret_code,
            ret_msg,
        )
        return []

    result = data.get("result")
    if not isinstance(result, dict):
        logger.warning("Bybit %s 回應缺少 result 或格式異常", endpoint)
        return []

    rows = result.get("list")
    if not isinstance(rows, list):
        logger.warning("Bybit %s 回應缺少 list 或格式異常", endpoint)
        return []

    return rows


async def get_usdt_perpetual_symbols(session: aiohttp.ClientSession) -> list[str]:
    """取得所有狀態為 Trading 的 USDT 永續合約清單。"""
    url = f"{BYBIT_BASE}/v5/market/instruments-info"
    params = {"category": "linear", "limit": 1000}
    data = await _safe_get_json(session, url, params, "instruments-info")

    rows = _extract_result_list(data, "instruments-info")
    symbols: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if (
            isinstance(symbol, str)
            and symbol.endswith("USDT")
            and item.get("status") == "Trading"
            and symbol not in EXCLUDED_SYMBOLS
        ):
            symbols.append(symbol)
    return symbols


async def get_tickers_24h(session: aiohttp.ClientSession) -> dict[str, dict]:
    """一次取回所有 linear 幣種的 24 小時行情資料。"""
    url = f"{BYBIT_BASE}/v5/market/tickers"
    params = {"category": "linear"}
    data = await _safe_get_json(session, url, params, "tickers")

    rows = _extract_result_list(data, "tickers")
    ticker_map: dict[str, dict] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if isinstance(symbol, str):
            ticker_map[symbol] = item
    return ticker_map


async def _fetch_klines_one(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    symbol: str,
    interval: str,
    limit: int = 3,
) -> list:
    """
    抓單一幣種的 K 線資料。
    回傳格式（每根）：[startTime, open, high, low, close, volume, turnover]
    由新到舊排列（index 0 = 最新/目前這根，index 1 = 前一根已收）。
    """
    url = f"{BYBIT_BASE}/v5/market/kline"
    params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit}
    async with semaphore:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
    return data.get("result", {}).get("list", [])


async def fetch_all_klines(
    session: aiohttp.ClientSession,
    symbols: list[str],
    interval: str,
) -> dict[str, list]:
    """並行抓取所有幣種的 K 線，回傳 {symbol: klines_list}。"""
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def fetch_one(sym: str):
        try:
            klines = await _fetch_klines_one(session, semaphore, sym, interval)
            return sym, klines
        except Exception as exc:
            logger.debug("抓取 %s [%s] K 線失敗: %s", sym, interval, exc)
            return sym, []

    pairs = await asyncio.gather(*[fetch_one(sym) for sym in symbols])
    return dict(pairs)
