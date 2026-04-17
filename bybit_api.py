import asyncio
import logging
import aiohttp
from config import BYBIT_BASE, CONCURRENCY, EXCLUDED_SYMBOLS

logger = logging.getLogger(__name__)


async def get_usdt_perpetual_symbols(session: aiohttp.ClientSession) -> list[str]:
    """取得所有狀態為 Trading 的 USDT 永續合約清單。"""
    url = f"{BYBIT_BASE}/v5/market/instruments-info"
    params = {"category": "linear", "limit": 1000}
    async with session.get(url, params=params) as resp:
        data = await resp.json()
    return [
        item["symbol"]
        for item in data["result"]["list"]
        if item["symbol"].endswith("USDT")
        and item["status"] == "Trading"
        and item["symbol"] not in EXCLUDED_SYMBOLS
    ]


async def get_tickers_24h(session: aiohttp.ClientSession) -> dict[str, dict]:
    """一次取回所有 linear 幣種的 24 小時行情資料。"""
    url = f"{BYBIT_BASE}/v5/market/tickers"
    params = {"category": "linear"}
    async with session.get(url, params=params) as resp:
        data = await resp.json()
    return {item["symbol"]: item for item in data["result"]["list"]}


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
