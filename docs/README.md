# Bybit 永續合約異常通知機器人

每 5 分鐘掃描 Bybit 所有 USDT 永續合約，符合條件即發送 Telegram 通知。

## 觸發條件（5m K 與 1h K 各自判斷）

| 條件 | 說明 |
|------|------|
| 成交量異常 | 目前 K 成交量 ≥ 前一根已收 K 的 **5 倍** |
| 漲跌異常 | 開盤→現價漲跌幅（絕對值）≥ **10%** |

任一成立即通知。兩者同時成立發「雙重異常」。

## 訊息範例

```
🔥【雙重異常】ORDIUSDT (1h)
Bybit 永續合約
過去 3600 秒價格上漲 17.0%
成交量倍數：8.3x（門檻 5x）
目前成交量：1,234,567 / 前一根：148,729
開盤：35.20 → 現價：41.18
24h 漲跌幅：+99.2%
```

## 專案結構

```
vol-alert/
├── main.py          # 主程式：排程 + 掃描邏輯
├── bybit_api.py     # Bybit API 非同步抓取
├── notifier.py      # Telegram 發送
├── config.py        # 設定（讀取 .env）
├── .env             # 金鑰（不可上傳 Git）
├── requirements.txt
└── docs/
    └── README.md
```

## 安裝與執行

```bash
pip install -r requirements.txt
py main.py
```

## 環境變數（.env）

```
TG_TOKEN=<BotFather 取得的 Token>
TG_CHAT_ID=<群組或頻道的 Chat ID>
```

## 調整設定

編輯 `config.py`：

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `VOL_MULTIPLIER` | `5.0` | 成交量倍數門檻 |
| `PRICE_CHANGE_THRESHOLD` | `0.10` | 漲跌幅門檻（10%） |
| `CONCURRENCY` | `30` | 同時發出的 API 請求數 |
