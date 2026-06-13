# MGO vs GO Gold Arbitrage — Complete Starter Tutorial

Step-by-step: from an empty machine to running the `gold_mgo_go_arbitrage.ipynb` simulation,
and an honest answer to *"how much money do I need to trade this?"*

```text
The trade:   10 x MGOM26  ==  1 x GOM26
             (same gold, same June expiry, both cash-settle on the same LBMA price)
The bet:     when the mini prints away from the big contract, buy the cheap one,
             sell the rich one, wait for the spread to close. Convergence is contractual.
```

---

## Step 1 — Accounts and API access

You need two things before any code:

1. **A TFEX derivatives account** with a broker that supports Settrade (you already have this —
   `SETTRADE_BROKER_ID` in your `.env`).
2. **A Settrade Open API application**. Follow the official quick start:
   <https://developer.settrade.com/open-api/document/reference/sdkv2/introduction/python/quick-start>
   - Register on the Settrade Open API portal through your broker.
   - Create an *app* → you receive **`app_id`**, **`app_secret`**, **`app_code`**, and use your
     broker's **`broker_id`**.
   - Choose the **Investor** app type (that is what the SDK's `Investor` class logs in as).

> ⚠️ **API etiquette (learned the hard way in this project):**
> - The market-data endpoint allows roughly **10 requests/minute**. Burst past it and the API
>   **kicks your session** and locks the app out for many minutes.
> - Keep ~6 seconds between requests, and cache everything you fetch.
> - One credential set is also used by the Railway bid/ask logger — avoid hammering the API
>   from two places at once.

---

## Step 2 — Project setup with `uv`

```bash
# 1. Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. From the project root (this repo), install everything from pyproject.toml
cd set-bot-lab
uv sync

# (a fresh project would instead be:)
# uv init my-gold-arb && cd my-gold-arb
# uv add settrade-v2 python-dotenv pandas numpy matplotlib jupyterlab ipykernel
```

Create `.env` in the project root (NEVER commit it):

```text
SETTRADE_APP_ID=your_app_id
SETTRADE_APP_SECRET=your_app_secret
SETTRADE_APP_CODE=your_app_code
SETTRADE_BROKER_ID=your_broker_id
```

---

## Step 3 — Jupyter setup

```bash
uv run jupyter lab
```

- Open `gold_mgo_go_arbitrage.ipynb` and pick the default Python 3 (ipykernel) kernel —
  `uv run` guarantees it is the project venv with `settrade-v2` installed.
- The notebook caches all fetched candles in `gold_candles_cache/` (plain CSV).
  First run = 2 API requests (~15 s). Re-runs on the same day = **0 requests**.

---

## Step 4 — Verify the API connection (30 seconds)

Run this in a notebook cell or `uv run python -` before anything else:

```python
import os
from dotenv import load_dotenv
from settrade_v2 import Investor

load_dotenv()
investor = Investor(
    app_id=os.environ["SETTRADE_APP_ID"],
    app_secret=os.environ["SETTRADE_APP_SECRET"],
    app_code=os.environ["SETTRADE_APP_CODE"],
    broker_id=os.environ["SETTRADE_BROKER_ID"],
    is_auto_queue=False,
)
md = investor.MarketData()
r = md.get_candlestick(symbol="GOM26", interval="60m",
                       start="2026-06-12T00:00:00", end="2026-06-12T23:59:59")
print(len(r["time"]), "bars — API OK")
```

If you see `Session unavailable. Status[Kicked]` or `Service is not ready yet`: stop, wait
10–15 minutes, and slow down your request rate. Do not retry in a tight loop.

---

## Step 5 — The strategy in plain words

| Rule | Detail |
|---|---|
| **Watch** | `sibling_spread = MGOM26 close − GOM26 close` (USD per troy oz) |
| **Enter** | when `|spread| × 300 THB` > all round-trip costs + buffer (≈ **1.5 USD/oz** at default costs) |
| | spread **negative** (mini cheap) → **buy 10 MGO + sell 1 GO** |
| | spread **positive** (mini rich) → **sell 10 MGO + buy 1 GO** |
| **Exit** | when the spread is back inside ±0.1 USD (one tick) → close all 11 legs |
| **Why it converges** | both contracts cash-settle on the *same* LBMA AM fixing, the *same* day — the spread must die at expiry; the bet is *when*, not *if* |

No z-score, no statistics — the same "gap pays more than all costs" logic as
`simple_spread_strategy.ipynb`.

---

## Step 6 — Run the simulation

Run `gold_mgo_go_arbitrage.ipynb` top to bottom. What each section tells you:

| Section | Question it answers |
|---|---|
| Step 1 fetch | do I have data since the 25 May launch? |
| Step 2 adoption | how liquid is the mini vs the big? (~4–5% of GO-equivalent volume so far) |
| Step 3 sibling spread | how far does the mini stray? (±2–6 USD/oz routinely; extremes −6.3/+20) |
| Step 5 backtest | what would the rules have earned? |
| P&L section | the equity curve and the honest scoreboard |

Result of the 25 May → 12 Jun window: **14 closed trades, +5,480 THB per pair, ~288 THB/day**
— all from 1-hour candle closes (see the warnings inside the notebook before believing it).

---

## Step 7 — Starter cost: the money you actually need

Three buckets — fees, margin, and buffer. **Numbers marked (assumption) must be replaced with
your broker's real numbers.**

### 7.1 Fees per round trip (one pair = 10 MGO + 1 GO)

| Item | Per side | Round trip (×2) |
|---|---|---|
| 10 × MGO @ ~8 THB (assumption: exchange 0.75–1.50 + data 0.20 + brokerage + VAT) | 80 THB | 160 THB |
| 1 × GO @ ~65 THB (assumption: exchange ≤14 + data 2 + brokerage + VAT) | 65 THB | 130 THB |
| **Fees total** | | **≈ 290 THB** |
| Book crossing (assumption: mini 0.3 USD wide, big 0.2 USD wide) | | ≈ 150 THB |
| **Total cost per round trip** | | **≈ 440 THB ⇒ spread must move ≥ 1.5 USD/oz** |

### 7.2 Margin (the big bucket)

TFEX rule: **Initial Margin = 1.75 × Maintenance Margin** for local investors
([TFEX gold margin page](https://www.tfex.co.th/en/products/gold-margin.html) — the live
baht amounts are published by Thailand Clearing House; check the current rate sheet or ask
your broker).

```text
pair margin = 10 × IM(MGO) + 1 × IM(GO)        ... if your broker margins each leg separately
            ≈ 2 × IM(GO)                       (because 10 minis ≈ 1 big in notional)
```

- Example (assumption): if IM(GO) ≈ 100,000 THB and IM(MGO) ≈ 10,000 THB →
  pair margin ≈ **200,000 THB**.
- **Ask your broker one key question:** *"do you give spread/offset margin credit for
  10 MGO vs 1 GO?"* If they recognise it as a hedged spread, the requirement can drop a lot.
  If not, you post both sides in full.

### 7.3 Buffer (do not skip this)

You hold both legs while waiting (median 14 hours, longest 87 hours in the backtest). Gold
moving 2–3% against one leg generates margin calls **even though the pair is hedged**, because
variation margin is settled per contract in cash daily. Keep **≥ 50% of the pair margin** as
free cash.

### 7.4 The starter table

| Item | Amount (example assumptions) |
|---|---|
| Pair margin (10 MGO + 1 GO, no offset credit) | ~200,000 THB |
| Cash buffer (50%) | ~100,000 THB |
| Round-trip costs you'll pay per trade | ~440 THB |
| **Suggested starting capital for ONE pair** | **~300,000 THB** |
| Paper income at the observed rate | ~288 THB/day ≈ 2.7% / 19 days on margin |

---

## Step 8 — Before any real order (checklist)

1. **Replace candle closes with real quotes.** Point the Railway logger at
   `MGOM26 / GOM26` (it already captured test snapshots) and confirm the spread exists in the
   *executable* bid/ask, not just in last-trade prints.
2. **Check the mini's depth.** 10 MGO lots may be the entire book on a weeks-old product.
   The visible spread is worthless if your own order moves it.
3. **Confirm real fees and margin** with your broker (especially spread margin credit and
   whether MGO brokerage is really ~1/10 of GO).
4. **Mind the expiry.** GOM26 / MGOM26 stop trading near end of June 2026 — the June pair has
   limited runway; the same trade rolls to U26 (September).
5. **Start with exactly one pair**, place the GO leg first (deeper book), the mini legs
   immediately after, and never leave an unhedged overnight position.
6. These notebooks place **no orders** — keep it that way until every box above is ticked.

---

## Sources

- [Settrade Open API — Python SDK quick start](https://developer.settrade.com/open-api/document/reference/sdkv2/introduction/python/quick-start)
- [TFEX — Gold Online Futures contract specification](https://www.tfex.co.th/en/products/precious-metal/gold-online-futures/contract-specification)
- [TFEX — gold futures margin page (IM = 1.75 × MM rule)](https://www.tfex.co.th/en/products/gold-margin.html)
- [Bangkok Post — MGO launch, 25 May 2026](https://www.bangkokpost.com/business/general/3257838/tfex-preps-mini-gold-online-futures-contracts-for-may-25)
- This repo: `gold_mgo_go_arbitrage.ipynb` (simulation), `simple_spread_strategy.ipynb`
  (the same entry/exit logic on the USD pair), `ARBITRAGE_TUTORIAL.md` (general risk notes).
