# labs-setbot-tutorial

A hands-on tutorial for new students on two **market-neutral** trading strategies built on real
Thai-derivatives data:

- **The USD dollar spread** — Binance TH `USDTTHB` vs TFEX USD futures (`USDM26`): the same dollar
  priced in baht in two places. *Statistical* arbitrage — it usually reverts, but nothing forces it.
- **The gold mini/big arbitrage** — TFEX `MGO` (mini) vs `GO` (big) gold futures: 10 minis = 1 big,
  both cash-settling on the *same* gold price. *True convergence* arbitrage — the gap must close at expiry.

> **Every notebook comes with its results already saved.** Open any `.ipynb`, `.html`, or `.md`
> and read top to bottom — all charts and tables are there. You do **not** need to run anything,
> and you don't need any data, account, or API key to follow along.

## 👉 Where to start

New here? The two **"from zero to simulation" walkthroughs** are the gentlest, most complete way
in — read one end to end first, then dip into the deeper studies:

- **[Step 5 — USD spread, from zero](step_basic_5_usdtthb_walkthrough.ipynb)** — the friendly
  complete version of the USD strategy.
- **[Step 6 — Gold arbitrage, from zero](step_basic_6_gold_arbitrage.ipynb)** — the same teaching
  style on the gold pair.

## The full course

Each step is provided three ways: the notebook (`.ipynb`), a designed web page (`.html`), and
plain Markdown (`.md`).

### Part A — The USD dollar spread strategy

| # | Notebook | What you learn | Data |
|---|----------|----------------|------|
| 1 | [`step_basic_1_spread`](step_basic_1_spread.ipynb) | The two markets and the **spread**, on 1-minute candles. | Public |
| 2 | [`step_basic_2_strategy`](step_basic_2_strategy.ipynb) | The **strategy**: costs, a backtest, order-book liquidity. | Real bid/ask |
| 3 | [`step_basic_3_fee_tiers`](step_basic_3_fee_tiers.ipynb) | Five **VIP fee tiers** and the **return %**, year-to-date. | Public |
| 4 | [`step_basic_4_fee_tiers_real`](step_basic_4_fee_tiers_real.ipynb) | Fee tiers on **real bid/ask**: maker vs taker, break-even fee. | Real bid/ask |
| 5 | [`step_basic_5_usdtthb_walkthrough`](step_basic_5_usdtthb_walkthrough.ipynb) | ⭐ **From zero to a running simulation** — the complete guided version. | Real bid/ask |

### Part B — The gold mini/big arbitrage (sibling strategy)

| # | Notebook | What you learn | Data |
|---|----------|----------------|------|
| 6 | [`step_basic_6_gold_arbitrage`](step_basic_6_gold_arbitrage.ipynb) | ⭐ **From zero to simulation** on `10 × MGO = 1 × GO` gold convergence. | TFEX candles |

📄 **[`GOLD_MGO_GO_TUTORIAL.md`](GOLD_MGO_GO_TUTORIAL.md)** — the gold strategy's plain-text setup
guide (accounts, costs, margin, and "how much capital do I need?"). Pairs with Step 6.

📡 **[`THE_DATA_LOGGER.md`](THE_DATA_LOGGER.md)** — where the **real bid/ask** behind steps 2, 4,
and 5 comes from: the `settrade-bidask-railway` service that logs the live order book to PostgreSQL.

## Setup with `uv` (only needed if you want to *re-run* a notebook)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv (once)
uv sync                                            # build the environment from uv.lock
uv run jupyter lab                                 # open any step and run it
```

Re-running needs credentials — copy `.env.example` to `.env` and fill in:

- **Settrade API keys** — for the TFEX candle reference (steps 1, 3) and the gold candles (step 6).
- **`DATABASE_URL`** — a PostgreSQL database the [data logger](THE_DATA_LOGGER.md) has filled with
  captured bid/ask (steps 2, 4, 5).

Just reading the course needs none of this — the saved outputs are complete.

## What this is (and isn't)

- **Is:** honest, worked examples of market-neutral strategies on real Thai-market data, with every
  cost, margin, and assumption stated out loud.
- **Isn't:** trading advice or an order-placing bot. No notebook places an order, and the numbers
  describe specific (often quiet) data windows — treat the percentages as a method to learn, not a
  promised yield.

## Project layout

```text
labs-setbot-tutorial/
├── README.md                          ← you are here
├── THE_DATA_LOGGER.md                 ← the real-bid/ask data source (steps 2, 4, 5)
├── GOLD_MGO_GO_TUTORIAL.md            ← the gold strategy setup guide (step 6)
├── pyproject.toml / uv.lock           ← the uv environment
├── .env.example                       ← credentials, only needed to re-run
├── render_tutorial_html.py            ← notebook -> designed HTML
├── step_basic_1..4_*.ipynb            ← USD strategy, research depth
├── step_basic_5_usdtthb_walkthrough.* ← USD strategy, from-zero walkthrough
└── step_basic_6_gold_arbitrage.*      ← gold arbitrage, from-zero walkthrough
```

### Notebook lineage

`spread_usdthb_1m_30d` → step 1 · `simple_spread_strategy` → step 2 · `vip_fee_strategy_1m_ytd` →
step 3 · `vip_fee_strategy_real_bidask` → step 4 · `usdtthb_spread_tutorial` → step 5 ·
`gold_mgo_go_tutorial` → step 6.
