# Bybit 永續合約異常通知機器人

依不同週期（5m / 1h / 1d）掃描 Bybit 所有 USDT 永續合約，符合條件即發送 Telegram 通知。

## 觸發條件（5m / 1h / 1d 各自判斷）

| 條件 | 說明 |
|------|------|
| 強價格異常 | 最新已收 K 開盤→收盤漲跌幅（絕對值）≥ **10%** |
| 價格+成交量異常 | 最新已收 K 漲跌幅（絕對值）≥ **5%** 且成交量 ≥ 前一根已收 K 的 **10 倍** |

任一成立即通知；兩者同時成立會標記為雙重異常。

## 訊息範例

```
🔥【雙重異常】ORDIUSDT (1h)
Bybit 永續合約
過去 3600 秒價格上漲 17.0%
成交量倍數：8.3x（門檻 10x）
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
| `VOL_MULTIPLIER` | `10.0` | 成交量倍數門檻（條件：價格 >= 5% 時使用） |
| `PRICE_CHANGE_THRESHOLD` | `0.05` | 漲跌幅門檻（5%，搭配成交量條件） |
| `PRICE_CHANGE_STRONG` | `0.10` | 漲跌幅門檻（10%，不看成交量） |
| `CONCURRENCY` | `30` | 同時發出的 API 請求數 |
