# Botify

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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the localhost dashboard

```bash
PYTHONPATH=src python src/main.py
```

Then open:

```text
http://127.0.0.1:5000
```

You can also run the compatibility launcher:

```bash
PYTHONPATH=. python bot.py
```

## API endpoints

- `GET /` — dashboard.
- `GET /api/tick` — fetch one BTC price tick, advance the simulator, and return JSON state.
- `GET /api/state` — return current JSON state without advancing the simulator.

## Step-by-step roadmap

1. **Local BTC simulator and dashboard** — current milestone.
2. Add backtesting from historical BTC candles.
3. Add paper-trading mode with Binance testnet or a local exchange emulator.
4. Add API key handling, signed Binance Futures connectivity, and order reconciliation.
5. Add production safety gates: manual confirmation, max leverage, max notional, kill switch, error alerts, and audit logs.
6. Only after BTC is stable, consider adding other symbols.

## Tests

```bash
PYTHONPATH=src pytest
```
