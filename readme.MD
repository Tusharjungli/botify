# Botify

Botify is a BTC-only cryptocurrency grid bot project. The current milestone is a **safe localhost simulator and backtester**: it shows real-time BTC grid behavior, risk limits, open positions, and simulated PnL without connecting private Binance API keys or placing live orders.

> Risk note: crypto futures trading can lose money quickly. This repository starts with simulation and backtesting only so the strategy, dashboard, and guardrails can be tested before any live Binance integration.

## Current status

- ✅ BTC-only simulator dashboard for `BTCUSDT`.
- ✅ Public Binance BTC price feed with deterministic offline fallback.
- ✅ Simulated balance, realized PnL, unrealized PnL, win rate, paper orders, fills, open positions, and recent trades.
- ✅ Moderate-risk defaults: low per-order risk, separate open-position and pending-order capacity, balanced long/short range ladders, tighter passive grid entries, total committed-notional cap, spike-tick order cancel/cooldown, stale pending-order cleanup, 2x leverage by default, daily loss lock, profit lock, stop loss, trailing profit, and trend-flip exits.
- ✅ Beginner-friendly BTC backtest command and headless paper-session collector.
- ✅ Dashboard pause/resume, reset, risk settings, quick synthetic backtest controls, live-readiness checks, profit-stage guidance, and BTC price chart.
- ✅ Local Binance Futures-style emulator with symbol filters, mark price status, liquidation estimates, and a read-only testnet adapter skeleton.
- ❌ No private Binance API keys yet.
- ❌ No live orders yet.

## Why the first step is simulation

Binance Futures Grid automates buy/sell orders at preset intervals inside a configured range and supports auto/manual parameters and leverage. Botify keeps those grid ideas but adds local transparency and custom controls before live trading.

## Install

Create and activate a virtual environment, then install requirements.

### Mac/Linux/Git Bash

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the localhost dashboard

### Mac/Linux/Git Bash

```bash
PYTHONPATH=src python src/main.py
```

### Windows PowerShell

```powershell
$env:PYTHONPATH="src"
python src/main.py
```

Then open:

```text
http://127.0.0.1:5000
```

You can also run the compatibility launcher:

```bash
PYTHONPATH=. python bot.py
```


## Dashboard controls

The localhost dashboard includes beginner-friendly controls:

- **Pause / Resume** — stop or continue automatic simulator ticks without closing the server.
- **Reset simulation** — clear simulated balance changes, open positions, closed trades, and tick history.
- **Cancel paper orders** — cancel all pending local paper orders without closing simulated positions.
- **Emergency stop** — cancel pending paper orders and lock new simulated entries until reset.
- **Run quick synthetic backtest** — run a 500-candle deterministic backtest directly from the browser.
- **Trade Diagnostics** — inspect open exposure, pending exposure, committed notional cap usage, separate position/pending slot usage, long/short split, gross profit/loss, profit factor, expectancy, trend-flip exits, grid width, grid spacing, and nearest target distance.
- **Live Readiness** — blocks moving to testnet/live until the run has enough closed trades, positive equity, a closed-trade edge, cap compliance, no risk locks, a public Binance price source, and a passing backtest gate.
- **Profit Stages** — explain when unrealized PnL can become realized profit: entry fill, first exit, 30+ trade sample, positive paper edge, and confirming backtest.
- **Run Review** — summarize whether the current sample is still too small, whether trend-flip exits are frequent, whether the run is not live-ready, and how much simulated exposure is open.
- **Paper Orders / Fills** — show pending local limit orders and recently filled simulated exchange orders before they become positions. In range mode, pending orders are built as a balanced ladder below and above the current BTC price rather than repeatedly stacking one side; the first entry is intentionally closer than one full grid step so quiet one-hour sessions can still get realistic paper fills.
- **Export trades CSV** — download simulated closed trades for spreadsheet review after longer localhost runs. For safer overnight collection, use the headless paper-session command below so data is written to disk even if the browser is closed.
- **Risk Settings** — show the active BTC-only grid, leverage, risk, stop, trailing, spike guard, and daily lock settings.
- **BTC Price Chart** — draw recent BTC ticks, grid range, open entry levels, targets, and stops with stacked labels so crowded markers remain readable.

These controls are still simulation-only. They do not connect private Binance API keys and do not place live orders.

## Run a BTC backtest

After the dashboard works, run a historical/synthetic BTC backtest from the terminal:

```bash
PYTHONPATH=src python -m botify.backtest
```

By default, Botify tries public Binance `BTCUSDT` 5-minute candles and automatically falls back to deterministic synthetic prices if Binance is unavailable.

Useful examples:

```bash
# Force synthetic data so the command works offline
PYTHONPATH=src python -m botify.backtest --source synthetic --limit 500

# Try public Binance candles with a different interval
PYTHONPATH=src python -m botify.backtest --source binance --interval 15m --limit 1000
```

The report shows ending equity, total return, realized/unrealized PnL, closed trades, win rate, profit factor, max drawdown, biggest win/loss, open positions, and whether risk locks disabled new entries.


## Collect paper-trading data without keeping the browser open

For serious tuning, do **not** judge the bot from a 1-2 hour dashboard run. Use the headless paper-session collector so Botify writes `report.json`, `latest_snapshot.json`, and `trades.csv` under `data/paper_sessions/` while it runs. The dashboard can be closed; only the terminal process needs to stay alive.

```bash
# Fast local smoke run with deterministic prices
PYTHONPATH=src python -m botify.paper_session --source synthetic --ticks 500 --target-closed-trades 5

# Paper collect from Binance public ticker, saving every 20 ticks
PYTHONPATH=src python -m botify.paper_session --source auto --sleep-seconds 3 --ticks 10000 --target-closed-trades 30 --save-every 20
```

Do not connect live Binance keys just because one short run is green. The current live-readiness gate expects at least 30 closed simulated trades, positive equity, positive expectancy/profit factor, exposure within caps, no risk locks, and a passing backtest before moving to Binance Futures **testnet**. Live funds should come only after testnet order placement and reconciliation are proven stable.


## Tune parameters before testnet

A short paper run can look promising while the backtest gate still fails. Before Binance testnet, run the parameter sweep and compare safer settings across the same historical/synthetic price series.

```bash
PYTHONPATH=src python -m botify.optimize --source synthetic --limit 500 --top 10
PYTHONPATH=src python -m botify.optimize --source binance --interval 5m --limit 1000 --top 10
```

The sweep writes `data/optimization/sweep_report.json` and `data/optimization/sweep_results.csv`. Treat only variants with enough trades, ending equity above start, and profit factor above 1.05 as paper-test candidates; do not use a green short paper sample to skip testnet.

## API endpoints

- `GET /` — dashboard.
- `GET /api/tick` — fetch one BTC price tick, advance the simulator, and return JSON state.
- `GET /api/state` — return current JSON state without advancing the simulator, including paper orders and fills.
- `GET /api/control` — return pause status and tick count.
- `POST /api/control/toggle-pause` — pause or resume automatic ticking.
- `POST /api/control/reset` — reset simulated account state.
- `POST /api/control/cancel-orders` — cancel all open local paper orders.
- `POST /api/control/emergency-stop` — cancel open paper orders and disable new simulated entries.
- `POST /api/backtest?limit=500` — run a quick synthetic dashboard backtest.
- `GET /api/trades.csv` — download simulated closed trades as CSV.

## Step-by-step roadmap

1. **Local BTC simulator and dashboard** — done.
2. **BTC backtesting command** — done.
3. **Dashboard controls: pause/resume, reset, cancel orders, emergency stop, settings panel, quick backtest, price chart, diagnostics, run review, paper order lifecycle, and CSV export** — done.
4. **Headless paper-session collector with durable JSON/CSV outputs** — done.
5. **Parameter sweep for safer backtest-first tuning** — done.
6. Use the live-readiness panel as the gate for moving from local simulation to Binance Futures testnet; do not connect live keys while any gate is failing.
7. Expand Binance-style local controls with richer order reconciliation, funding-rate modeling, partial fills, slippage, spike/outlier reports, and exchange filters.
8. Add signed read-only Binance Futures testnet calls for exchange info, account info, positions, mark price, and user-stream reconciliation.
9. Add testnet-only order placement behind manual confirmation and kill-switch checks.
10. Add production safety gates: manual confirmation, exchange-side max leverage checks, kill switch, error alerts, and audit logs.
11. Only after BTC is stable, consider adding other symbols.

## Tests

```bash
PYTHONPATH=src pytest
```
