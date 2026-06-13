> **Tutorial note:** this is the data source behind **Step 2** (`step_basic_2_strategy`) and
> **Step 4** (`step_basic_4_fee_tiers_real`). Those notebooks read the real bid/ask this service
> captures. You don't need to deploy it to read the course — this page just explains where the
> numbers come from. The full deployable service lives in `../set-bot-lab/settrade-bidask-railway/`.

# Settrade Bid/Ask 10-Level Collector

Python service for Railway that subscribes to Settrade Open API realtime bid/offer data and saves the full 10-level order book to PostgreSQL.

The service also exposes a small HTTP API so Railway has a healthcheck target and you can inspect the latest saved order book. Optional collectors can store Binance TH depth and Bybit TradFi `USDTHB+` quotes in the same database.

## Why Python

Settrade provides an official Python SDK v2 (`settrade-v2`), and its realtime MQTT helpers already include:

- `Investor(...).RealtimeDataConnection()`
- `subscribe_bid_offer(symbol, on_message=...)`
- `subscribe_price_info(symbol, on_message=...)`
- `Investor(...).MarketData().get_candlestick(...)`

Using Python keeps the collector close to the official SDK examples and avoids reimplementing Settrade MQTT auth.

Official references:

- Bid/offer realtime: <https://developer.settrade.com/open-api/api-reference/reference/sdkv2/python/market-mqtt-realtime-data/3_subscribeBidOffer>
- Price info realtime: <https://developer.settrade.com/open-api/api-reference/reference/sdkv2/python/market-mqtt-realtime-data/2_subscribePriceInfo>
- Realtime getting started: <https://developer.settrade.com/open-api/api-reference/reference/sdkv2/python/market-mqtt-realtime-data/1_gettingStart>
- Historical candlestick: <https://developer.settrade.com/open-api/api-reference/reference/sdkv2/python/market-historical-data/2_getCandlestick>

## What Gets Saved

On every bid/offer event, the app inserts:

- One row in `bidask_snapshots`
- Twenty rows in `bidask_levels`: bid levels 1-10 and ask levels 1-10
- The raw Settrade payload as JSONB for debugging and future fields

If `SUBSCRIBE_PRICE_INFO=true`, price info events are saved to `price_info_ticks`.

Optional candlestick backfills are saved to `candlesticks`.

If `ENABLE_BINANCE_TH_COLLECTOR=true`, Binance TH depth snapshots are saved into the same `bidask_snapshots` and `bidask_levels` tables with `source='binance_th'`.

If `ENABLE_BYBIT_TRADFI_COLLECTOR=true`, Bybit TradFi quotes such as `USDTHB+` are saved to `quote_ticks` and also mirrored into `bidask_levels` as level 1 only with `source='bybit_tradfi'`. Bybit does not expose a 5-level order book for `USDTHB+`; its public TradFi config marks `showOrderBook=false`.

## Project Structure

```text
.
├── Procfile
├── railway.toml
├── runtime.txt
├── pyproject.toml
├── src/set_bidask_service/
│   ├── main.py              # FastAPI app and Railway web process
│   ├── collector.py         # Settrade realtime subscriber
│   ├── bybit.py             # Bybit TradFi USDTHB+ quote collector
│   ├── repository.py        # PostgreSQL inserts and queries
│   ├── schema.py            # Database tables and indexes
│   ├── transforms.py        # Bid/ask and candle payload parsing
│   └── backfill_candles.py  # Optional historical candlestick loader
└── tests/
```

## 1. Configure Environment Variables

Copy the example file for local development:

```bash
cp .env.example .env
```

Fill in `.env` locally and Railway variables in production:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
SETTRADE_APP_ID=your_app_id
SETTRADE_APP_SECRET=your_app_secret
SETTRADE_APP_CODE=ALGO
SETTRADE_BROKER_ID=your_broker_id
SETTRADE_ENV=prod
SETTRADE_SYMBOLS=USDM26,MGOM26,MGOU26,GOM26,GOU26
ENABLE_COLLECTOR=true
SUBSCRIBE_PRICE_INFO=true
SNAPSHOT_MIN_INTERVAL_MS=0
LOG_LEVEL=INFO
ENABLE_BINANCE_TH_COLLECTOR=false
BINANCE_TH_SYMBOLS=USDTTHB,PAXGUSDT
BINANCE_TH_DEPTH_LIMIT=10
BINANCE_TH_POLL_INTERVAL_SECONDS=1.0
ENABLE_BYBIT_TRADFI_COLLECTOR=false
BYBIT_TRADFI_SYMBOLS=USDTHB+
BYBIT_TRADFI_POLL_INTERVAL_SECONDS=1.0
BYBIT_TRADFI_CANDLE_INTERVAL=30
BYBIT_TRADFI_CANDLE_LIMIT=2
BYBIT_TRADFI_CANDLE_POLL_INTERVAL_SECONDS=60.0
```

Notes:

- Do not commit `.env`.
- Use `SETTRADE_ENV=uat`, `SETTRADE_APP_CODE=SANDBOX`, and `SETTRADE_BROKER_ID=SANDBOX` for sandbox credentials.
- `SETTRADE_SYMBOLS` is comma-separated. Use only symbols your Settrade account can access.
- `SNAPSHOT_MIN_INTERVAL_MS=0` saves every bid/offer event. Increase it, for example to `250`, if the database write volume is too high.
- `BINANCE_TH_SYMBOLS` is comma-separated and uses Binance TH symbols such as `USDTTHB`, `PAXGUSDT`, or `BTCTHB`. Binance TH public market data does not require an API key.
- `BYBIT_TRADFI_SYMBOLS` is comma-separated and keeps the plus sign, for example `USDTHB+`. This feed is quote-only for `USDTHB+`; Bybit does not provide 5-level depth for this TradFi symbol.

## 2. Run Locally

Install dependencies:

```bash
uv sync
```

Start the service:

```bash
uv run uvicorn set_bidask_service.main:app --reload --host 0.0.0.0 --port 8000
```

If your environment has not installed the package yet, run with the source app directory explicitly:

```bash
uv run uvicorn --app-dir src set_bidask_service.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- <http://localhost:8000/health>
- <http://localhost:8000/ready>
- <http://localhost:8000/latest/AOT>
- <http://localhost:8000/docs>

The app creates tables automatically on startup when `DATABASE_URL` is configured. `/health` is a liveness endpoint for Railway and should return HTTP 200 as long as the web server is running. `/ready` checks database and Settrade configuration and returns HTTP 503 until required variables are present.

## 3. Deploy To Railway

Create a Railway project and attach PostgreSQL, or use an existing PostgreSQL URL.

Add the variables from step 1 in Railway:

```bash
railway variables set DATABASE_URL="postgresql://..."
railway variables set SETTRADE_APP_ID="..."
railway variables set SETTRADE_APP_SECRET="..."
railway variables set SETTRADE_APP_CODE="ALGO"
railway variables set SETTRADE_BROKER_ID="..."
railway variables set SETTRADE_ENV="prod"
railway variables set SETTRADE_SYMBOLS="USDM26,MGOM26,MGOU26,GOM26,GOU26"
railway variables set ENABLE_COLLECTOR="true"
railway variables set SUBSCRIBE_PRICE_INFO="true"
railway variables set ENABLE_BINANCE_TH_COLLECTOR="true"
railway variables set BINANCE_TH_SYMBOLS="USDTTHB,PAXGUSDT"
railway variables set ENABLE_BYBIT_TRADFI_COLLECTOR="true"
railway variables set BYBIT_TRADFI_SYMBOLS="USDTHB+"
```

Deploy:

```bash
railway up
```

Railway will run:

```bash
uvicorn --app-dir src set_bidask_service.main:app --host 0.0.0.0 --port $PORT
```

After deploy, check:

```bash
curl https://YOUR-RAILWAY-DOMAIN/health
curl https://YOUR-RAILWAY-DOMAIN/latest/AOT
```

Run only one Railway replica for the collector. Multiple replicas will subscribe and insert duplicate realtime rows.

## 4. Query PostgreSQL

Latest saved snapshot:

```sql
SELECT id, symbol, received_at, bid_flag, ask_flag
FROM bidask_snapshots
WHERE symbol = 'AOT'
ORDER BY received_at DESC
LIMIT 5;
```

Levels for one snapshot:

```sql
SELECT side, level, price, volume
FROM bidask_levels
WHERE snapshot_id = 123
ORDER BY side, level;
```

Best bid/ask over time:

```sql
SELECT
    s.symbol,
    s.received_at,
    MAX(CASE WHEN l.side = 'bid' AND l.level = 1 THEN l.price END) AS best_bid,
    MAX(CASE WHEN l.side = 'ask' AND l.level = 1 THEN l.price END) AS best_ask
FROM bidask_snapshots s
JOIN bidask_levels l ON l.snapshot_id = s.id
WHERE s.symbol = 'AOT'
GROUP BY s.id, s.symbol, s.received_at
ORDER BY s.received_at DESC
LIMIT 100;
```

Latest Binance TH 10-level book:

```sql
SELECT *
FROM latest_bidask_10_levels
WHERE source = 'binance_th'
  AND symbol = 'USDTTHB'
ORDER BY level;
```

Latest Settrade TFEX 10-level book:

```sql
SELECT *
FROM latest_bidask_10_levels
WHERE source = 'settrade'
  AND symbol = 'USDM26'
ORDER BY level;
```

Latest Bybit TradFi `USDTHB+` quote:

```sql
SELECT *
FROM latest_quote_ticks
WHERE source = 'bybit_tradfi'
  AND symbol = 'USDTHB+';
```

Latest Bybit TradFi `USDTHB+` mirrored level-1 bid/ask:

```sql
SELECT *
FROM latest_bidask_10_levels
WHERE source = 'bybit_tradfi'
  AND symbol = 'USDTHB+'
  AND level = 1
ORDER BY level;
```

## 5. Gold Spread Pair: TFEX Gold Futures (MGO / GO) vs Binance TH PAXG/USDT

All three markets quote gold in **US dollars per troy ounce**, so their books are directly comparable:

- **Binance TH `PAXGUSDT`**: PAXG is a gold token where 1 PAXG = 1 troy oz of LBMA gold. Quoted in USDT (≈ 1 USD).
- **TFEX `MGO` Mini Gold Online Futures** and **`GO` Gold Online Futures** (via Settrade): cash-settled futures on 99.5% gold. Same product design; only the multiplier differs.

Key contract facts (from TFEX specs):

| Item | MGO (Mini) | GO |
|---|---|---|
| Symbol example | `MGOM26` = June 2026 | `GOM26` = June 2026 |
| Contract months | Quarterly only: H=Mar, M=Jun, U=Sep, Z=Dec; 2 nearest quarters listed | same |
| Quotation | USD per troy ounce, 1 decimal | same |
| Multiplier | 30 (quanto: P&L is THB 30 per 1.0 USD move, no FX) | 300 (THB 300 per 1.0 USD move) |
| Tick size (minimum price step) | 0.1 USD/oz = THB 3 per contract | 0.1 USD/oz = THB 30 per contract |
| Daily price limit | ±10% of last settlement (expands to ±20% after a halt) | same |
| Sessions | 09:45–12:30, 14:15–16:55, night 18:50–03:00 | same |
| Last trading day | Business day before the last business day of the contract month, trading ends 16:30 | same |
| Settlement | Cash, to LBMA Gold AM Fixing (ICE Benchmark Administration), no FX applied | same |

Note: the tick size is the **minimum price step**, not a fee. Trading fees are brokerage +
exchange fee + VAT, charged per contract by your broker.

Collector setup: add `MGOM26,MGOU26,GOM26,GOU26` to `SETTRADE_SYMBOLS` and `PAXGUSDT` to
`BINANCE_TH_SYMBOLS`. Logging both quarterly contracts keeps data flowing across expiry
(e.g. `MGOM26`/`GOM26` stop trading near end of June 2026; the U26 contracts continue).

Sizing note for any spread analysis (quanto contracts, THB P&L vs USDT P&L): 1 PAXG has ~1 USDT
of P&L per 1 USD move. At USDTHB ≈ 33 a delta-matched pair is roughly
**1 MGO ↔ 0.9 PAXG** and **1 GO ↔ 9 PAXG**, not 1:1.

Latest MGO book (same query works for `GOM26`):

```sql
SELECT *
FROM latest_bidask_10_levels
WHERE source = 'settrade'
  AND symbol = 'MGOM26'
ORDER BY level;
```

Latest PAXG/USDT book:

```sql
SELECT *
FROM latest_bidask_10_levels
WHERE source = 'binance_th'
  AND symbol = 'PAXGUSDT'
ORDER BY level;
```

## 6. Optional Candlestick Backfill

Fetch historical candles through Settrade SDK and save them to the `candlesticks` table:

```bash
uv run python -m set_bidask_service.backfill_candles \
  --symbol AOT \
  --interval 1m \
  --limit 500
```

With a date range:

```bash
uv run python -m set_bidask_service.backfill_candles \
  --symbol AOT \
  --interval 1m \
  --start "2026-06-01T00:00:00+07:00" \
  --end "2026-06-11T23:59:59+07:00"
```

## 7. Local Checks

```bash
uv run pytest
uv run ruff check .
```
