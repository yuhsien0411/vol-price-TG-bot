import os
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN: str = os.getenv("TG_TOKEN", "")
TG_CHAT_ID: str = os.getenv("TG_CHAT_ID", "")

BYBIT_BASE = "https://api.bybit.com"

# 監控週期設定：label 顯示用、api 傳給 Bybit、window_sec 訊息說明用
INTERVALS = [
    {"label": "5m",  "api": "5",  "window_sec": 300,   "interval_ms": 300_000},
    {"label": "1h",  "api": "60", "window_sec": 3600,  "interval_ms": 3_600_000},
    {"label": "1d",  "api": "D",  "window_sec": 86400, "interval_ms": 86_400_000, "enable_volume": False},
]

VOL_MULTIPLIER: float = 10.0          # 成交量異常門檻（倍）（條件1）
PRICE_CHANGE_THRESHOLD: float = 0.05  # 價格波動門檻（5%，條件1用）
PRICE_CHANGE_STRONG: float = 0.10     # 價格波動門檻（10%，條件2用）
CONCURRENCY: int = 30                 # 同時發出的 API 請求數

# 不監控的交易對
EXCLUDED_SYMBOLS: set[str] = {
    "USDEUSDT",
    "USDCUSDT",
}
