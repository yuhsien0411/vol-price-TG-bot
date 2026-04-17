"""
Bybit 永續合約異常通知機器人
觸發條件（5m / 1h / 1d 各自判斷）：
  1. 最新已收 K 線成交量 >= 前一根已收 K 線成交量的 5 倍
  2. 最新已收 K 線漲跌幅（開盤→收盤）絕對值 >= 10%
播報時機：
  - 5m K：每 5 分鐘整（:00, :05, :10 ...）
  - 1h K：每小時整點（xx:00）
  - 1d K：每日 00:00（Asia/Taipei）
"""

import asyncio
import logging
import aiohttp
from apscheduler.schedulers.blocking import BlockingScheduler

from bybit_api import get_usdt_perpetual_symbols, get_tickers_24h, fetch_all_klines
from notifier import send_message
from config import INTERVALS, VOL_MULTIPLIER, PRICE_CHANGE_THRESHOLD, PRICE_CHANGE_STRONG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 去重記憶：{"{symbol}_{interval_label}": candle_start_time}
_alerted: dict[str, str] = {}

TG_MAX_CHARS = 3800  # Telegram 限制 4096，留緩衝


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def _build_summaries(label: str, kind: str, rows: list[str]) -> list[str]:
    """
    將同一類別的多個幣種組成彙整訊息，超過 TG_MAX_CHARS 自動分頁。
    """
    total = len(rows)
    if kind == "volume":
        base_header = f"🚨 成交量異常【{label}】共 {total} 個"
    else:
        base_header = f"📊 價格異常【{label}】共 {total} 個"

    divider = "─" * 20

    pages: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for row in rows:
        if current_len + len(row) + 1 > TG_MAX_CHARS and current:
            pages.append(current)
            current = []
            current_len = 0
        current.append(row)
        current_len += len(row) + 1
    if current:
        pages.append(current)

    total_pages = len(pages)
    messages: list[str] = []
    for i, page_rows in enumerate(pages, 1):
        page_tag = f" ({i}/{total_pages})" if total_pages > 1 else ""
        header = base_header + page_tag
        body = "\n".join(page_rows)
        messages.append(f"{header}\n{divider}\n{body}")
    return messages


async def scan(target_intervals: list[dict]) -> None:
    """
    掃描指定週期清單，抓 K 線 → 判斷條件 → 發彙整通知。
    target_intervals: INTERVALS 的子集，例如只傳 5m 或只傳 1h。
    """
    labels = [cfg["label"] for cfg in target_intervals]
    logger.info("開始掃描：%s", ", ".join(labels))

    buckets: dict[str, dict[str, list[str]]] = {
        cfg["label"]: {"volume": [], "price": []} for cfg in target_intervals
    }

    async with aiohttp.ClientSession() as session:
        symbols = await get_usdt_perpetual_symbols(session)
        tickers = await get_tickers_24h(session)
        logger.info("共 %d 個 USDT 永續合約", len(symbols))

        for interval_cfg in target_intervals:
            label        = interval_cfg["label"]
            api_interval = interval_cfg["api"]
            enable_volume = interval_cfg.get("enable_volume", True)

            klines_map = await fetch_all_klines(session, symbols, api_interval)

            triggered_count = 0
            for symbol in symbols:
                klines = klines_map.get(symbol, [])
                if len(klines) < 3:
                    continue

                # 僅使用「已收盤」K 線比較：
                # - curr: 最新一根已收
                # - prev: 再前一根已收
                # klines[0] 是目前形成中的 K（可能未收），故不納入判斷
                curr = klines[1]
                prev = klines[2]

                curr_vol    = float(curr[5])
                prev_vol    = float(prev[5])
                curr_open   = float(curr[1])
                curr_close  = float(curr[4])

                price_chg_raw = (curr_close - curr_open) / curr_open if curr_open else 0
                price_abs     = abs(price_chg_raw)

                # 條件 1：成交量 >= 前一根 VOL_MULTIPLIER 倍 且 價格波動 >= PRICE_CHANGE_THRESHOLD (5%)
                cond1 = (
                    prev_vol > 0
                    and curr_vol >= prev_vol * VOL_MULTIPLIER
                    and price_abs >= PRICE_CHANGE_THRESHOLD
                )
                # 條件 2：純價格波動 >= PRICE_CHANGE_STRONG (10%)，不看成交量
                cond2 = price_abs >= PRICE_CHANGE_STRONG

                if not (cond1 or cond2):
                    continue

                # 同一根 K 線內只通知一次
                dedup_key   = f"{symbol}_{label}"
                candle_time = curr[0]
                if _alerted.get(dedup_key) == candle_time:
                    continue
                _alerted[dedup_key] = candle_time

                triggered_count += 1
                ticker     = tickers.get(symbol, {})
                chg24h     = float(ticker.get("price24hPcnt", 0)) * 100
                chg24h_str = _fmt_pct(chg24h)
                curr_chg_str = _fmt_pct(price_chg_raw * 100)
                vol_ratio    = curr_vol / prev_vol if prev_vol > 0 else 0
                direction    = "▲" if price_chg_raw >= 0 else "▼"
                pct_str      = f"{direction}{price_abs*100:.1f}%"
                dual_mark    = "🔥" if cond1 and cond2 else ("⚡" if cond1 else "")

                # 彙整邏輯：
                # - 成交量列表：僅 cond1 成立的列（成交量 + 價格 >=5%）
                # - 價格列表：cond1 或 cond2 都放進來（價格 >=5% 且量大，或價格 >=10%）
                if cond1 and enable_volume:
                    buckets[label]["volume"].append(
                        f"{dual_mark}{symbol}  {vol_ratio:.1f}x"
                        f"   {curr_close}  {curr_chg_str}  24h {chg24h_str}"
                    )
                if cond1 or cond2:
                    buckets[label]["price"].append(
                        f"{dual_mark}{symbol}  {pct_str}"
                        f"  {curr_open}→{curr_close}  24h {chg24h_str}"
                    )

            logger.info("%s：%d 個異常", label, triggered_count)

        for interval_cfg in target_intervals:
            label = interval_cfg["label"]
            for kind in ("volume", "price"):
                rows = buckets[label][kind]
                if not rows:
                    continue
                msgs = _build_summaries(label, kind, rows)
                for msg in msgs:
                    send_message(msg)
                logger.info("已發送 %s %s 彙整（%d 個幣，%d 則）", label, kind, len(rows), len(msgs))

    logger.info("掃描完成")


# 各週期的 config 快速存取
_CFG_5M = next(c for c in INTERVALS if c["label"] == "5m")
_CFG_1H = next(c for c in INTERVALS if c["label"] == "1h")
_CFG_1D = next(c for c in INTERVALS if c["label"] == "1d")


def run_5m() -> None:
    asyncio.run(scan([_CFG_5M]))


def run_1h() -> None:
    asyncio.run(scan([_CFG_1H]))


def run_1d() -> None:
    asyncio.run(scan([_CFG_1D]))


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Taipei")

    # 5m K：每 5 分鐘整（:00, :05, :10 ...）
    scheduler.add_job(run_5m, "cron", minute="*/5", id="job_5m")

    # 1h K：每小時整點（xx:00）
    scheduler.add_job(run_1h, "cron", minute=0, id="job_1h")

    # 1d K：每日 00:00
    scheduler.add_job(run_1d, "cron", hour=0, minute=0, id="job_1d")

    logger.info("排程啟動（時區：Asia/Taipei）")
    logger.info("  5m K：每 5 分鐘整")
    logger.info("  1h K：每小時整點")
    logger.info("  1d K：每日 00:00")
    logger.info("啟動不立即播報，等待下一次排程時間...")

    scheduler.start()
