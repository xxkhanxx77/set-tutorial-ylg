# Tutorial: USDT/THB vs TFEX USD Futures — From Zero to Simulation

**A complete, runnable, step-by-step guide** — the simple version of
`simple_spread_strategy.ipynb`, in the same format as the gold tutorial. By the end you will
have:

1. A working `uv` project connected to **your own quote database** (the Railway bid/ask logger).
2. An understanding of the cross-market trade:

```text
Binance TH USDTTHB   and   TFEX USD Futures (USDM26)   both price: USD in THB
spread = Binance price - TFEX price -> should be ~0, sometimes it is not
```

3. A running simulation on **real captured bid/ask quotes** (not candles!).
4. An honest answer to: **how much capital do I need, and why fees decide everything?**

> Every code cell below actually runs. No orders are ever placed.

## Step 1 — The data source: your own bid/ask logger

This strategy dies or lives on **executable** prices. Candle closes are last trades — only
real best-bid/best-ask shows what you could actually earn. This project logs both books 24/7:

| Feed | Symbol | Source |
|---|---|---|
| TFEX USD Futures | `USDM26` | Settrade realtime (`subscribe_bid_offer`) |
| Binance TH spot | `USDTTHB` | Binance TH websocket/REST |

The Railway service stores every update in Postgres (`bidask_snapshots` + `bidask_levels`,
10 levels deep). All this notebook needs is the `DATABASE_URL`.

> The longer the logger runs, the better this notebook gets — the opportunity is the rare
> wide-spread day (like 27 May 2026), and you want data when it happens.

## Step 2 — Project setup with `uv`

```bash
# 1. install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. this repo: install all dependencies from pyproject.toml
cd set-bot-lab
uv sync
```

Create `.env` in the project root — **never commit it**:

```text
DATABASE_URL=postgresql://user:pass@host:port/db    # your Railway Postgres
```

## Step 3 — Start Jupyter

```bash
uv run jupyter lab
```

Open this notebook and keep the default Python 3 (ipykernel) kernel — `uv run` guarantees
the project venv with `psycopg2` installed.

## Step 4 — Verify the database connection

One query: how many quotes do we have, and how fresh are they?


```python
import os
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import psycopg2
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
pd.set_option("display.width", 160)
plt.rcParams["figure.dpi"] = 120

TFEX_SYMBOL = "USDM26"
BINANCE_SYMBOL = "USDTTHB"

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
health = pd.read_sql("""
SELECT source, COUNT(*) AS quotes,
       MIN(received_at) AT TIME ZONE 'Asia/Bangkok' AS first_quote,
       MAX(received_at) AT TIME ZONE 'Asia/Bangkok' AS last_quote
FROM bidask_snapshots
WHERE (source = 'settrade'   AND symbol = %(t)s)
   OR (source = 'binance_th' AND symbol = %(b)s)
GROUP BY source
""", conn, params={"t": TFEX_SYMBOL, "b": BINANCE_SYMBOL})
conn.close()
print("Database OK\n")
display(health)
```

    Database OK
    



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>source</th>
      <th>quotes</th>
      <th>first_quote</th>
      <th>last_quote</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>settrade</td>
      <td>23450</td>
      <td>2026-06-11 12:39:39.176473</td>
      <td>2026-06-12 22:19:22.266230</td>
    </tr>
    <tr>
      <th>1</th>
      <td>binance_th</td>
      <td>34198</td>
      <td>2026-06-11 12:47:39.709905</td>
      <td>2026-06-12 22:19:26.274136</td>
    </tr>
  </tbody>
</table>
</div>


## Step 5 — The strategy in plain words

| Rule | Detail |
|---|---|
| **Watch** | the *executable edge*, computed from real bid/ask (not mids!) |
| | `edge_short = binance_bid − tfex_ask` (Binance expensive: sell USDT there, buy futures) |
| | `edge_long = tfex_bid − binance_ask` (Binance cheap: buy USDT there, sell futures) |
| **Enter** | when `edge − all round-trip costs ≥ buffer` |
| **Exit** | when the gap is gone (closing costs ~nothing) → close both legs |
| **Honest label** | this is *statistical* arbitrage — a bet on mean reversion, **not** risk-free. The two products settle differently and never converge by contract (unlike the MGO/GO gold pair). |

No z-score, no statistics. One contract = 1,000 USD; TFEX tick 0.01 THB = 10 THB/contract.

## Step 6 — Turn fees into ONE number: round-trip cost per USD

The Binance TH fee tier is the whole game
([fee schedule](https://www.binance.th/en/faq/spot-trading/4900a0792af24f5e853e2373b84f94e7);
`USDTTHB` is an *exchange pair*):

| Tier | Taker/side | Maker/side | 30-day volume needed |
|---|---|---|---|
| VIP 0 | 0.25% | 0.25% | — |
| VIP 2 | 0.20% | 0.15% | ≥ 500k USD |
| VIP 4 | 0.10% | 0.10% | ≥ 3M USD |

Set YOUR tier below — everything downstream updates.


```python
BINANCE_FEE_RATE = 0.0025        # your real tier! 0.25% = VIP 0 taker
TFEX_COST_PER_SIDE_THB = 0.025   # ~25 THB per contract per side (brokerage+exchange+VAT) / 1,000 USD
ENTRY_BUFFER_THB = 0.01          # safety on top of costs
EXIT_TOLERANCE_THB = 0.01
MAX_QUOTE_AGE_SECONDS = 2        # never compare quotes further apart than this

APPROX_PRICE = 32.7              # refined from real data below
binance_rt = 2 * BINANCE_FEE_RATE * APPROX_PRICE
tfex_rt = 2 * TFEX_COST_PER_SIDE_THB
ROUND_TRIP_COST_THB = binance_rt + tfex_rt

print(f"Binance round trip : {binance_rt:.4f} THB/USD  ({BINANCE_FEE_RATE:.2%}/side)")
print(f"TFEX round trip    : {tfex_rt:.4f} THB/USD")
print(f"TOTAL              : {ROUND_TRIP_COST_THB:.4f} THB/USD "
      f"(= {ROUND_TRIP_COST_THB * 1000:,.0f} THB per contract)")
print(f"=> the edge must exceed {ROUND_TRIP_COST_THB + ENTRY_BUFFER_THB:.4f} THB/USD to enter")
```

    Binance round trip : 0.1635 THB/USD  (0.25%/side)
    TFEX round trip    : 0.0500 THB/USD
    TOTAL              : 0.2135 THB/USD (= 214 THB per contract)
    => the edge must exceed 0.2235 THB/USD to enter


## Step 7 — Load and align the real quotes

Pull level-1 bid/ask for both markets, then attach to every Binance quote the **most recent**
TFEX quote — but only if it is younger than `MAX_QUOTE_AGE_SECONDS`. Comparing a fresh price
with a stale one creates fake spreads.


```python
conn = psycopg2.connect(os.environ["DATABASE_URL"])
raw = pd.read_sql("""
SELECT s.source, s.received_at,
  MAX(l.price) FILTER (WHERE l.side = 'bid' AND l.level = 1) AS bid,
  MAX(l.price) FILTER (WHERE l.side = 'ask' AND l.level = 1) AS ask
FROM bidask_snapshots s
JOIN bidask_levels l ON l.snapshot_id = s.id
WHERE (s.source = 'settrade'   AND s.symbol = %(t)s)
   OR (s.source = 'binance_th' AND s.symbol = %(b)s)
GROUP BY s.id, s.source, s.received_at
ORDER BY s.received_at
""", conn, params={"t": TFEX_SYMBOL, "b": BINANCE_SYMBOL})
conn.close()

raw["received_at"] = pd.to_datetime(raw["received_at"], utc=True).dt.tz_convert("Asia/Bangkok")
raw[["bid", "ask"]] = raw[["bid", "ask"]].astype(float)

tfex = (raw[raw.source == "settrade"]
        .rename(columns={"bid": "tfex_bid", "ask": "tfex_ask"})
        [["received_at", "tfex_bid", "tfex_ask"]].sort_values("received_at"))
binance = (raw[raw.source == "binance_th"]
           .rename(columns={"bid": "binance_bid", "ask": "binance_ask"})
           [["received_at", "binance_bid", "binance_ask"]].sort_values("received_at"))

pairs = pd.merge_asof(binance, tfex, on="received_at", direction="backward",
                      tolerance=pd.Timedelta(seconds=MAX_QUOTE_AGE_SECONDS)).dropna().reset_index(drop=True)

print(f"Matched quote pairs: {len(pairs):,}")
print(f"Window (Bangkok):    {pairs.received_at.min()} -> {pairs.received_at.max()}")
```

    Matched quote pairs: 13,157
    Window (Bangkok):    2026-06-12 11:40:04.946531+07:00 -> 2026-06-12 22:19:24.069159+07:00


## Step 8 — The spread and the executable edges

Shown two ways: the mid-spread in **percent** (how far apart the markets look) and the
executable edges in **THB per USD** (what you could really capture crossing both books).


```python
pairs["binance_mid"] = (pairs.binance_bid + pairs.binance_ask) / 2
pairs["tfex_mid"] = (pairs.tfex_bid + pairs.tfex_ask) / 2
pairs["mid_spread"] = pairs.binance_mid - pairs.tfex_mid
pairs["mid_spread_pct"] = pairs.mid_spread / pairs.tfex_mid * 100
pairs["edge_short_usdt"] = pairs.binance_bid - pairs.tfex_ask
pairs["edge_long_usdt"] = pairs.tfex_bid - pairs.binance_ask

avg_price = pairs.binance_mid.mean()
ROUND_TRIP_COST_THB = 2 * BINANCE_FEE_RATE * avg_price + 2 * TFEX_COST_PER_SIDE_THB
entry_bar = ROUND_TRIP_COST_THB + ENTRY_BUFFER_THB

import matplotlib.dates as mdates

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
ts = pairs.received_at

axes[0].plot(ts, pairs.binance_mid, color="darkorange", lw=0.8, label="Binance TH USDTTHB mid")
axes[0].plot(ts, pairs.tfex_mid, color="steelblue", lw=0.8, label=f"TFEX {TFEX_SYMBOL} mid")
axes[0].set_title("Both markets price USD in THB")
axes[0].set_ylabel("THB/USD")
axes[0].legend(fontsize=8)

axes[1].plot(ts, pairs.mid_spread_pct, color="purple", lw=0.8)
axes[1].axhline(0, color="black", lw=0.8)
axes[1].set_title("Mid spread in PERCENT of the TFEX price")
axes[1].set_ylabel("%")

axes[2].plot(ts, pairs.edge_short_usdt, color="crimson", lw=0.8, label="edge_short (Binance expensive)")
axes[2].plot(ts, pairs.edge_long_usdt, color="seagreen", lw=0.8, label="edge_long (Binance cheap)")
axes[2].axhline(entry_bar, color="black", ls="--", lw=1, label=f"entry bar {entry_bar:.3f} THB")
axes[2].axhline(0, color="black", lw=0.8)
axes[2].set_title("Executable edge BEFORE fees — must cross the dashed bar to trade")
axes[2].set_ylabel("THB per USD")
axes[2].legend(fontsize=8)

# timestamps on the x-axis (Bangkok time)
bkk = ts.dt.tz
axes[2].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=14))
axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M", tz=bkk))
fig.autofmt_xdate(rotation=30)
plt.tight_layout()
plt.show()

print(pairs[["mid_spread_pct", "edge_short_usdt", "edge_long_usdt"]].describe().round(4).to_string())
print(f"\nEntry bar at your fee tier: {entry_bar:.4f} THB/USD | "
      f"best edge in data: {max(pairs.edge_short_usdt.max(), pairs.edge_long_usdt.max()):.4f}")
```


    
![png](step_basic_5_usdtthb_walkthrough_files/step_basic_5_usdtthb_walkthrough_11_0.png)
    


           mid_spread_pct  edge_short_usdt  edge_long_usdt
    count      13157.0000       13157.0000       13157.000
    mean           0.0672           0.0109          -0.033
    std            0.0704           0.0232           0.023
    min           -0.0612          -0.0400          -0.100
    25%            0.0153          -0.0100          -0.050
    50%            0.0611           0.0100          -0.030
    75%            0.1070           0.0300          -0.020
    max            0.2754           0.0800           0.010
    
    Entry bar at your fee tier: 0.2236 THB/USD | best edge in data: 0.0800


## Step 9 — Run the simulation

Same ~25-line backtest as every notebook in this series. P&L per USD =
`entry edge + closing edge − round-trip costs`, from real bid/ask on both ends.


```python
def run_backtest(df: pd.DataFrame, round_trip_cost: float,
                 entry_buffer: float, exit_tolerance: float) -> pd.DataFrame:
    position, trades = None, []
    for row in df.itertuples():
        if position is None:
            if row.edge_short_usdt - round_trip_cost >= entry_buffer:
                position = {"side": "short_usdt_binance_long_tfex",
                            "entry_ts": row.received_at, "entry_edge": row.edge_short_usdt}
            elif row.edge_long_usdt - round_trip_cost >= entry_buffer:
                position = {"side": "long_usdt_binance_short_tfex",
                            "entry_ts": row.received_at, "entry_edge": row.edge_long_usdt}
        else:
            closing = (row.edge_long_usdt if position["side"].startswith("short")
                       else row.edge_short_usdt)
            if closing >= -exit_tolerance:
                pnl = position["entry_edge"] + closing - round_trip_cost
                trades.append({**position, "exit_ts": row.received_at, "exit_edge": closing,
                               "pnl_thb_per_contract": pnl * 1000})
                position = None
    return pd.DataFrame(trades)


trades = run_backtest(pairs, ROUND_TRIP_COST_THB, ENTRY_BUFFER_THB, EXIT_TOLERANCE_THB)

if trades.empty:
    print(f"0 trades at your fee tier ({BINANCE_FEE_RATE:.2%}/side). HONEST and expected in")
    print("a quiet window: the typical edge (0.01-0.04 THB) is smaller than the cost bar.")
    print("\nThe 5 best real moments (closest misses):")
    top = pairs.assign(best_edge=pairs[["edge_short_usdt", "edge_long_usdt"]].max(axis=1))
    display(top.nlargest(5, "best_edge")
            [["received_at", "binance_bid", "binance_ask", "tfex_bid", "tfex_ask",
              "best_edge", "mid_spread_pct"]].round(4))
else:
    print(f"{len(trades)} trades | total {trades.pnl_thb_per_contract.sum():,.0f} THB per contract")
    display(trades.round(4))
    t = trades.sort_values("exit_ts").reset_index(drop=True)
    t["cum"] = t.pnl_thb_per_contract.cumsum()
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.step(t.exit_ts, t.cum, where="post", color="seagreen", lw=2)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Cumulative P&L per contract")
    ax.set_ylabel("THB")
    plt.tight_layout()
    plt.show()
```

    0 trades at your fee tier (0.25%/side). HONEST and expected in
    a quiet window: the typical edge (0.01-0.04 THB) is smaller than the cost bar.
    
    The 5 best real moments (closest misses):


    /var/folders/zk/fvx2zb7x7hs3f_tfxv9lwyvc0000gn/T/ipykernel_54733/3423543026.py:32: UserWarning: obj.round has no effect with datetime, timedelta, or period dtypes. Use obj.dt.round(...) instead.
      "best_edge", "mid_spread_pct"]].round(4))



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>received_at</th>
      <th>binance_bid</th>
      <th>binance_ask</th>
      <th>tfex_bid</th>
      <th>tfex_ask</th>
      <th>best_edge</th>
      <th>mid_spread_pct</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>12524</th>
      <td>2026-06-12 21:54:27.932412+07:00</td>
      <td>32.77</td>
      <td>32.78</td>
      <td>32.68</td>
      <td>32.69</td>
      <td>0.08</td>
      <td>0.2754</td>
    </tr>
    <tr>
      <th>12525</th>
      <td>2026-06-12 21:54:29.035307+07:00</td>
      <td>32.77</td>
      <td>32.78</td>
      <td>32.68</td>
      <td>32.69</td>
      <td>0.08</td>
      <td>0.2754</td>
    </tr>
    <tr>
      <th>12527</th>
      <td>2026-06-12 21:54:31.299629+07:00</td>
      <td>32.77</td>
      <td>32.78</td>
      <td>32.68</td>
      <td>32.69</td>
      <td>0.08</td>
      <td>0.2754</td>
    </tr>
    <tr>
      <th>12528</th>
      <td>2026-06-12 21:54:32.425899+07:00</td>
      <td>32.77</td>
      <td>32.78</td>
      <td>32.68</td>
      <td>32.69</td>
      <td>0.08</td>
      <td>0.2754</td>
    </tr>
    <tr>
      <th>12529</th>
      <td>2026-06-12 21:54:33.532562+07:00</td>
      <td>32.77</td>
      <td>32.78</td>
      <td>32.68</td>
      <td>32.69</td>
      <td>0.08</td>
      <td>0.2754</td>
    </tr>
  </tbody>
</table>
</div>


### What if your fee tier were better?

Same data, same rules — only the Binance fee changes. This table is why the VIP tier is the
whole game (full study: `vip_fee_strategy_real_bidask.ipynb`).


```python
rows = []
for label, fee in [("VIP0 taker", 0.0025), ("VIP2 taker", 0.0020),
                   ("VIP2 maker*", 0.0015), ("VIP4", 0.0010), ("free (ref)", 0.0)]:
    rt = 2 * fee * avg_price + 2 * TFEX_COST_PER_SIDE_THB
    t = run_backtest(pairs, rt, ENTRY_BUFFER_THB, EXIT_TOLERANCE_THB)
    rows.append({"tier": label, "fee_per_side": f"{fee:.2%}",
                 "entry_bar_thb_per_usd": round(rt + ENTRY_BUFFER_THB, 4),
                 "trades": len(t),
                 "total_pnl_thb_per_contract": round(t.pnl_thb_per_contract.sum()) if len(t) else 0})
display(pd.DataFrame(rows).set_index("tier"))
print("* maker also avoids crossing the Binance book width, but fills are not guaranteed.")
```


<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>fee_per_side</th>
      <th>entry_bar_thb_per_usd</th>
      <th>trades</th>
      <th>total_pnl_thb_per_contract</th>
    </tr>
    <tr>
      <th>tier</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>VIP0 taker</th>
      <td>0.25%</td>
      <td>0.2236</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>VIP2 taker</th>
      <td>0.20%</td>
      <td>0.1909</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>VIP2 maker*</th>
      <td>0.15%</td>
      <td>0.1582</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>VIP4</th>
      <td>0.10%</td>
      <td>0.1254</td>
      <td>0</td>
      <td>0</td>
    </tr>
    <tr>
      <th>free (ref)</th>
      <td>0.00%</td>
      <td>0.0600</td>
      <td>1</td>
      <td>20</td>
    </tr>
  </tbody>
</table>
</div>


    * maker also avoids crossing the Binance book width, but fills are not guaranteed.


## Step 10 — Starter capital: the "value to trade"

Per ONE TFEX contract (= 1,000 USD on each leg):

- **Binance leg** is spot — no leverage. To *sell* 1,000 USDT you must own it; to *buy* you
  hold the THB. Either way ≈ `1,000 × price` in capital.
- **TFEX leg** is a future — you post initial margin only
  (TFEX rule: IM = 1.75 × maintenance margin for local investors).
- **Buffer** — both legs are marked daily; keep free cash.

Replace the assumption below with your broker's current margin sheet.


```python
IM_TFEX_USD_THB = 1_200   # initial margin per USD futures contract (ASSUMPTION - ask broker!)
BUFFER_RATIO = 0.10       # free cash vs the Binance notional

binance_leg = 1000 * avg_price
buffer_cash = binance_leg * BUFFER_RATIO
starter = binance_leg + IM_TFEX_USD_THB + buffer_cash

summary = pd.DataFrame([
    ["Binance leg (1,000 USDT notional)", f"{binance_leg:,.0f} THB"],
    ["TFEX initial margin (1 contract)", f"{IM_TFEX_USD_THB:,.0f} THB"],
    [f"Cash buffer ({BUFFER_RATIO:.0%})", f"{buffer_cash:,.0f} THB"],
    ["SUGGESTED STARTING CAPITAL (1 contract)", f"{starter:,.0f} THB"],
    ["Round-trip cost at your tier", f"{ROUND_TRIP_COST_THB * 1000:,.0f} THB per contract"],
], columns=["item", "value"]).set_index("item")
display(summary)

print("Note the asymmetry vs the gold pair: here most capital sits in the SPOT leg.")
print("And remember the VIP volume rule: each round trip = 2,000 USD of Binance volume;")
print("VIP2 needs 500k USD / 30 days -> the tier itself must be earned.")
```


<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>value</th>
    </tr>
    <tr>
      <th>item</th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Binance leg (1,000 USDT notional)</th>
      <td>32,724 THB</td>
    </tr>
    <tr>
      <th>TFEX initial margin (1 contract)</th>
      <td>1,200 THB</td>
    </tr>
    <tr>
      <th>Cash buffer (10%)</th>
      <td>3,272 THB</td>
    </tr>
    <tr>
      <th>SUGGESTED STARTING CAPITAL (1 contract)</th>
      <td>37,197 THB</td>
    </tr>
    <tr>
      <th>Round-trip cost at your tier</th>
      <td>214 THB per contract</td>
    </tr>
  </tbody>
</table>
</div>


    Note the asymmetry vs the gold pair: here most capital sits in the SPOT leg.
    And remember the VIP volume rule: each round trip = 2,000 USD of Binance volume;
    VIP2 needs 500k USD / 30 days -> the tier itself must be earned.


## Step 11 — Before any real order (checklist)

1. **Confirm your real Binance TH fee tier** — at 0.25%/side this strategy does not trade;
   the entire opportunity lives at VIP rates (see the what-if table above).
2. **Keep the Railway logger running.** The edge is episodic — you need data on the wide days,
   and this notebook improves every day the logger runs.
3. **Check depth on both books** before sizing (`simple_spread_strategy.ipynb` Step 8 does
   this with 10-level data — TFEX is the bottleneck ~40% of the time).
4. **Respect TFEX sessions.** Binance trades 24/7, TFEX does not — a 3 a.m. edge cannot be
   hedged.
5. **Remember this never converges by contract.** Unlike MGO/GO gold, nothing forces this
   spread to zero — size like a bet, not like an arbitrage.
6. This notebook places **no orders**. Keep it that way until every box is ticked.

---

### Sources & companions

- [Binance TH fee schedule](https://www.binance.th/en/faq/spot-trading/4900a0792af24f5e853e2373b84f94e7)
- [Settrade Open API quick start](https://developer.settrade.com/open-api/document/reference/sdkv2/introduction/python/quick-start)
- This repo: `simple_spread_strategy.ipynb` (full study with liquidity/slippage) ·
  `vip_fee_strategy_real_bidask.ipynb` (fee-tier deep dive) ·
  `gold_mgo_go_tutorial.ipynb` (the gold sibling of this tutorial)
