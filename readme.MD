# Botify

Botify is a BTC-only cryptocurrency grid bot project. The current milestone is a **safe localhost simulator and backtester**: it shows real-time BTC grid behavior, risk limits, open positions, and simulated PnL without connecting private Binance API keys or placing live orders.

> Risk note: crypto futures trading can lose money quickly. This repository starts with simulation and backtesting only so the strategy, dashboard, and guardrails can be tested before any live Binance integration.

## Current status

codex/create-custom-binance-grid-trading-bot-9b1qhc

codex/create-custom-binance-grid-trading-bot-nrrk67
 main
Botify is a BTC-only cryptocurrency grid bot project. The current milestone is a **safe localhost simulator and backtester**: it shows real-time BTC grid behavior, risk limits, open positions, and simulated PnL without connecting private Binance API keys or placing live orders.

> Risk note: crypto futures trading can lose money quickly. This repository starts with simulation and backtesting only so the strategy, dashboard, and guardrails can be tested before any live Binance integration.

## Current status

- ✅ BTC-only simulator dashboard for `BTCUSDT`.
- ✅ Public Binance BTC price feed with deterministic offline fallback.
- ✅ Simulated balance, realized PnL, unrealized PnL, win rate, open positions, and recent trades.
- ✅ Moderate-risk defaults: low per-order risk, max open positions, 2x leverage by default, daily loss lock, profit lock, stop loss, trailing profit, and trend-flip exits.
- ✅ Beginner-friendly BTC backtest command.
- ✅ Dashboard pause/resume, reset, risk settings, and quick synthetic backtest controls.
codex/create-custom-binance-grid-trading-bot-9b1qhc
- ✅ Dashboard pause/resume, reset, risk settings, and quick synthetic backtest controls.
main
- ❌ No private Binance API keys yet.
- ❌ No live orders yet.

## Why the first step is simulation

Binance Futures Grid automates buy/sell orders at preset intervals inside a configured range and supports auto/manual parameters and leverage. Botify keeps those grid ideas but adds local transparency and custom controls before live trading.

## Install

Create and activate a virtual environment, then install requirements.

### Mac/Linux/Git Bash

codex/create-custom-binance-grid-trading-bot-9b1qhc

Botify is a BTC-only cryptocurrency grid bot project. The first milestone is a **safe localhost simulator**: it shows real-time BTC grid behavior, risk limits, open positions, and simulated PnL without connecting private Binance API keys or placing live orders.

> Risk note: crypto futures trading can lose money quickly. This repository starts with simulation only so the strategy, dashboard, and guardrails can be tested before any live Binance integration.

## Why the first step is simulation

Binance Futures Grid automates buy/sell orders at preset intervals inside a configured range and supports auto/manual parameters and leverage. Botify keeps those grid ideas but adds local transparency and custom controls before live trading:

- BTC-only enforcement (`BTCUSDT`) until the strategy is proven.
- Local dashboard you can run on `localhost`.
- Simulated balance, realized PnL, unrealized PnL, win rate, open positions, and recent trades.
- Moderate-risk defaults: low per-order risk, max open positions, 2x leverage cap by default, daily loss lock, profit lock, stop loss, trailing profit, and trend-flip exits.
- Public Binance BTC ticker when available, with deterministic offline fallback when public data is unavailable.
- No private API keys and no live orders in milestone 1.

## Install

main
main
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

 codex/create-custom-binance-grid-trading-bot-9b1qhc

codex/create-custom-binance-grid-trading-bot-nrrk67
 main
### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the localhost dashboard

### Mac/Linux/Git Bash

 codex/create-custom-binance-grid-trading-bot-9b1qhc


## Run the localhost dashboard

main
 main
```bash
PYTHONPATH=src python src/main.py
```

codex/create-custom-binance-grid-trading-bot-9b1qhc

codex/create-custom-binance-grid-trading-bot-nrrk67
 main
### Windows PowerShell

```powershell
$env:PYTHONPATH="src"
python src/main.py
```

codex/create-custom-binance-grid-trading-bot-9b1qhc


main
main
Then open:

```text
http://127.0.0.1:5000
```

You can also run the compatibility launcher:

```bash
PYTHONPATH=. python bot.py
```

codex/create-custom-binance-grid-trading-bot-9b1qhc

## Dashboard controls

The localhost dashboard includes beginner-friendly controls:

- **Pause / Resume** — stop or continue automatic simulator ticks without closing the server.
- **Reset simulation** — clear simulated balance changes, open positions, closed trades, and tick history.
- **Run quick synthetic backtest** — run a 500-candle deterministic backtest directly from the browser.
- **Risk Settings** — show the active BTC-only grid, leverage, risk, stop, trailing, and daily lock settings.

These controls are still simulation-only. They do not connect private Binance API keys and do not place live orders.


codex/create-custom-binance-grid-trading-bot-nrrk67
main
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

codex/create-custom-binance-grid-trading-bot-9b1qhc


main
 main
## API endpoints

- `GET /` — dashboard.
- `GET /api/tick` — fetch one BTC price tick, advance the simulator, and return JSON state.
- `GET /api/state` — return current JSON state without advancing the simulator.
 codex/create-custom-binance-grid-trading-bot-9b1qhc
- `GET /api/control` — return pause status and tick count.
- `POST /api/control/toggle-pause` — pause or resume automatic ticking.
- `POST /api/control/reset` — reset simulated account state.
- `POST /api/backtest?limit=500` — run a quick synthetic dashboard backtest.

## Step-by-step roadmap

1. **Local BTC simulator and dashboard** — done.
2. **BTC backtesting command** — done.
3. **Dashboard controls: pause/resume, reset, settings panel, and quick backtest** — done.
4. Add charting and trade/export improvements.
5. Add paper-trading mode with Binance testnet or a local exchange emulator.
6. Add API key handling, signed Binance Futures connectivity, and order reconciliation.
7. Add production safety gates: manual confirmation, max leverage, max notional, kill switch, error alerts, and audit logs.
8. Only after BTC is stable, consider adding other symbols.


## Step-by-step roadmap

codex/create-custom-binance-grid-trading-bot-nrrk67
1. **Local BTC simulator and dashboard** — done.
2. **BTC backtesting command** — done.
3. Improve dashboard controls: start/pause, reset, settings panel, and chart.
4. Add paper-trading mode with Binance testnet or a local exchange emulator.
5. Add API key handling, signed Binance Futures connectivity, and order reconciliation.
6. Add production safety gates: manual confirmation, max leverage, max notional, kill switch, error alerts, and audit logs.
7. Only after BTC is stable, consider adding other symbols.

1. **Local BTC simulator and dashboard** — current milestone.
2. Add backtesting from historical BTC candles.
3. Add paper-trading mode with Binance testnet or a local exchange emulator.
4. Add API key handling, signed Binance Futures connectivity, and order reconciliation.
5. Add production safety gates: manual confirmation, max leverage, max notional, kill switch, error alerts, and audit logs.
6. Only after BTC is stable, consider adding other symbols.
main
main

## Tests

```bash
PYTHONPATH=src pytest
```
