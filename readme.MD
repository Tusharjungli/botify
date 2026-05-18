# Botify

Botify is a BTC-only cryptocurrency grid bot project. The current milestone is a **safe localhost simulator and backtester**: it shows real-time BTC grid behavior, risk limits, open positions, and simulated PnL without connecting private Binance API keys or placing live orders.

> Risk note: crypto futures trading can lose money quickly. This repository starts with simulation and backtesting only so the strategy, dashboard, and guardrails can be tested before any live Binance integration.

## Current status

- ✅ BTC-only simulator dashboard for `BTCUSDT`.
- ✅ Public Binance BTC price feed with deterministic offline fallback.
- ✅ Simulated balance, realized PnL, unrealized PnL, win rate, paper orders, fills, open positions, and recent trades.
- ✅ Tuned neutral BTC grid defaults: two-sided range entries, maker-style limit orders away from market, stale-order cancellation, max open orders, low per-order risk, 2x leverage by default, daily loss lock, profit lock, stop loss, and trailing profit.
- ✅ Beginner-friendly BTC backtest command with CLI tuning knobs for grid range, levels, bias, take-profit steps, stop loss, and order age.
- ✅ Dashboard pause/resume, reset, risk settings, quick synthetic backtest controls, and BTC price chart.
- ❌ No private Binance API keys yet.
- ❌ No live orders yet.

## Why the first step is simulation

Binance Futures Grid automates buy/sell orders at preset intervals inside a configured range and supports auto/manual parameters and leverage. Botify keeps those grid ideas but adds local transparency and custom controls before live trading. The current defaults are deliberately simulation-first: Botify places buy limits below market and sell limits above market, cancels stale unfilled paper orders, and reports profit factor/drawdown so changes are judged by evidence rather than hope.

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
- **Trade Diagnostics** — inspect open exposure, long/short split, gross profit/loss, profit factor, expectancy, grid width, and nearest target distance.
- **Run Review** — summarize whether the current sample is still too small, whether closed-trade losses are larger than wins, and how much simulated exposure is open.
- **Paper Orders / Fills** — show pending local limit orders and recently filled simulated exchange orders before they become positions.
- **Export trades CSV** — download simulated closed trades for spreadsheet review after longer localhost runs.
- **Risk Settings** — show the active BTC-only grid, trading bias, max open orders, entry offset, order max age, leverage, risk, stop, trailing, and daily lock settings.
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

# Stress a different strategy angle without editing code
PYTHONPATH=src python -m botify.backtest --source synthetic --trading-bias LONG --range-pct 0.05 --grid-levels 12 --take-profit-grid-steps 3 --stop-loss-pct 0.05
```

The report shows ending equity, total return, realized/unrealized PnL, closed trades, win rate, profit factor, max drawdown, biggest win/loss, open positions, and whether risk locks disabled new entries. A profitable synthetic run is only a development signal, not proof of future live profit; test multiple intervals and market regimes before risking money.

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
4. Add paper-trading mode with Binance testnet or a richer local exchange emulator.
5. Add API key handling, signed Binance Futures connectivity, and order reconciliation.
6. Add production safety gates: manual confirmation, max leverage, max notional, kill switch, error alerts, and audit logs.
7. Only after BTC is stable, consider adding other symbols.

## Tests

```bash
PYTHONPATH=src pytest
```
