"""Localhost dashboard for the Botify BTC grid simulator."""

from __future__ import annotations

import json
codex/create-custom-binance-grid-trading-bot-9b1qhc
import math
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from .backtest import run_backtest, synthetic_closes

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

main
from .config import BotConfig
from .engine import GridEngine
from .market import BinancePublicPriceFeed, DeterministicPriceFeed, HybridPriceFeed

CONFIG = BotConfig()
engine = GridEngine(CONFIG)
 codex/create-custom-binance-grid-trading-bot-9b1qhc
CONFIG = BotConfig()
engine = GridEngine(CONFIG)

engine = GridEngine(BotConfig())
 main
price_feed = HybridPriceFeed(
    live_feed=BinancePublicPriceFeed(symbol="BTCUSDT"),
    fallback_feed=DeterministicPriceFeed(),
)
codex/create-custom-binance-grid-trading-bot-9b1qhc
state_lock = Lock()
paused = False
last_backtest: dict | None = None

 main

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Botify BTC Grid Simulator</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Arial, sans-serif; }
    body { margin: 0; background: #0b1020; color: #ecf2ff; }
    header { padding: 24px; background: linear-gradient(135deg, #172554, #111827); border-bottom: 1px solid #23304d; }
    main { padding: 24px; display: grid; gap: 18px; }
 codex/create-custom-binance-grid-trading-bot-9b1qhc
    .cards, .settings { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
    .card, .panel, table { background: #111827; border: 1px solid #23304d; border-radius: 16px; box-shadow: 0 16px 32px #0004; }
    .card, .panel { padding: 16px; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    button { border: 0; border-radius: 12px; padding: 12px 16px; color: #06111f; background: #38bdf8; font-weight: 800; cursor: pointer; }
    button.secondary { background: #a7f3d0; }
    button.warning { background: #fbbf24; }
    button:hover { filter: brightness(1.08); }
    .label { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { margin-top: 8px; font-size: 24px; font-weight: 800; }
    .small-value { margin-top: 8px; font-size: 18px; font-weight: 700; }

    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
    .card, table { background: #111827; border: 1px solid #23304d; border-radius: 16px; box-shadow: 0 16px 32px #0004; }
    .card { padding: 16px; }
    .label { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { margin-top: 8px; font-size: 24px; font-weight: 800; }
 main
    .good { color: #34d399; } .bad { color: #fb7185; } .warn { color: #fbbf24; }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 12px 14px; border-bottom: 1px solid #23304d; text-align: left; font-size: 14px; }
    th { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #1e293b; }
    .note { color: #a8b3c7; line-height: 1.5; max-width: 980px; }
    .status-line { min-height: 24px; color: #a8b3c7; }
 codex/create-custom-binance-grid-trading-bot-9b1qhc
    .status-line { min-height: 24px; color: #a8b3c7; }

 main
  </style>
</head>
<body>
  <header>
    <h1>Botify — BTCUSDT Grid Simulator</h1>
    <p class="note">Simulation only: no private Binance keys and no live orders. Public BTC price is used when available; otherwise Botify falls back to a deterministic local feed.</p>
  </header>
  <main>
 codex/create-custom-binance-grid-trading-bot-9b1qhc
    <section class="panel">
      <h2>Controls</h2>
      <div class="toolbar">
        <button id="pauseButton" onclick="togglePause()">Pause</button>
        <button class="warning" onclick="resetSimulation()">Reset simulation</button>
        <button class="secondary" onclick="runBacktest()">Run quick synthetic backtest</button>
      </div>
      <p class="status-line" id="statusLine">Loading dashboard state...</p>
    </section>
    <section class="cards" id="cards"></section>
    <section>
      <h2>Risk Settings</h2>
      <div class="settings" id="settings"></div>
    </section>
    <section>
      <h2>Quick Backtest Result</h2>
      <div class="cards" id="backtestCards"><article class="card"><div class="label">Status</div><div class="small-value">Click “Run quick synthetic backtest”.</div></article></div>
    </section>
    <section>

    <section class="cards" id="cards"></section>
    <section>
 main
      <h2>Open Positions</h2>
      <table><thead><tr><th>Side</th><th>Entry</th><th>Target</th><th>Stop</th><th>Qty</th><th>Unrealized</th></tr></thead><tbody id="positions"></tbody></table>
    </section>
    <section>
      <h2>Recent Closed Trades</h2>
      <table><thead><tr><th>Side</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Reason</th><th>Closed</th></tr></thead><tbody id="trades"></tbody></table>
    </section>
  </main>
<script>
const money = (n) => Number(n).toLocaleString(undefined, {style: 'currency', currency: 'USD'});
const num = (n, d=2) => Number(n).toLocaleString(undefined, {maximumFractionDigits: d});
function pnlClass(n) { return Number(n) >= 0 ? 'good' : 'bad'; }
 codex/create-custom-binance-grid-trading-bot-9b1qhc
async function postJson(path) {
  const response = await fetch(path, {method: 'POST'});
  if (!response.ok) throw new Error(`${path} failed with ${response.status}`);
  return response.json();
}
async function refresh() {
  const stateResponse = await fetch('/api/control');
  const control = await stateResponse.json();
  const response = await fetch(control.paused ? '/api/state' : '/api/tick');
  const data = await response.json();
  renderDashboard(data);
}
function renderDashboard(data) {
  document.getElementById('pauseButton').textContent = data.paused ? 'Resume' : 'Pause';
  document.getElementById('statusLine').textContent = data.paused
    ? 'Paused: Botify is not advancing new price ticks. Click Resume to continue.'
    : 'Running: Botify advances one simulated tick every refresh. No live orders are placed.';

async function refresh() {
  const response = await fetch('/api/tick');
  const data = await response.json();
 main
  document.getElementById('cards').innerHTML = [
    ['BTC Price', money(data.price), ''],
    ['Price Source', `<span class="pill">${data.price_source}</span>`, ''],
    ['Mode', `<span class="pill">${data.mode}</span>`, ''],
    ['Simulator', data.paused ? 'Paused' : 'Running', data.paused ? 'warn' : 'good'],
    ['Equity', money(data.equity), pnlClass(data.equity - data.config.starting_balance)],
    ['Balance', money(data.balance), ''],
    ['Realized PnL', money(data.realized_pnl), pnlClass(data.realized_pnl)],
    ['Unrealized PnL', money(data.unrealized_pnl), pnlClass(data.unrealized_pnl)],
    ['Daily PnL', `${num(data.daily_pnl_pct * 100)}%`, pnlClass(data.daily_pnl_pct)],
    ['Trading', data.trading_enabled ? 'Enabled' : 'Locked', data.trading_enabled ? 'good' : 'warn'],
    ['Win Rate', `${num(data.win_rate)}%`, ''],
    ['Closed Trades', data.closed_trades, ''],
  ].map(([label, value, klass]) => `<article class="card"><div class="label">${label}</div><div class="value ${klass}">${value}</div></article>`).join('');

  document.getElementById('settings').innerHTML = [
    ['Symbol', data.config.symbol],
    ['Starting Balance', money(data.config.starting_balance)],
    ['Grid Levels', data.config.grid_levels],
    ['Range', `${num(data.config.range_pct * 100)}%`],
    ['Leverage', `${num(data.config.leverage)}x`],
    ['Order Risk', `${num(data.config.base_order_risk_pct * 100)}%`],
    ['Max Open Positions', data.config.max_open_positions],
    ['Daily Loss Lock', `${num(data.config.max_daily_loss_pct * 100)}%`],
    ['Profit Lock', `${num(data.config.daily_profit_lock_pct * 100)}%`],
    ['Stop Loss', `${num(data.config.stop_loss_pct * 100)}%`],
    ['Trailing Stop', `${num(data.config.trailing_stop_pct * 100)}%`],
    ['Min Grid Profit', `${num(data.config.min_grid_profit_pct * 100)}%`],
  ].map(([label, value]) => `<article class="card"><div class="label">${label}</div><div class="small-value">${value}</div></article>`).join('');

  document.getElementById('positions').innerHTML = data.positions.length ? data.positions.map(p => `
    <tr><td>${p.side}</td><td>${money(p.entry_price)}</td><td>${money(p.target_price)}</td><td>${money(p.stop_price)}</td><td>${num(p.quantity, 6)}</td><td class="${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td></tr>
  `).join('') : '<tr><td colspan="6">No open positions yet.</td></tr>';

  document.getElementById('trades').innerHTML = data.trades.length ? data.trades.map(t => `
    <tr><td>${t.side}</td><td>${money(t.entry_price)}</td><td>${money(t.exit_price)}</td><td class="${pnlClass(t.pnl)}">${money(t.pnl)}</td><td>${t.reason}</td><td>${t.closed_at}</td></tr>
  `).join('') : '<tr><td colspan="6">No closed trades yet.</td></tr>';

  if (data.last_backtest) renderBacktest(data.last_backtest);
}
function renderBacktest(report) {
  document.getElementById('backtestCards').innerHTML = [
    ['Source', report.source, ''],
    ['Candles', report.candles, ''],
    ['Ending Equity', money(report.ending_equity), pnlClass(report.total_return_pct)],
    ['Total Return', `${num(report.total_return_pct)}%`, pnlClass(report.total_return_pct)],
    ['Closed Trades', report.closed_trades, ''],
    ['Win Rate', `${num(report.win_rate)}%`, ''],
    ['Profit Factor', report.profit_factor === null ? 'infinite' : num(report.profit_factor), ''],
    ['Max Drawdown', `${num(report.max_drawdown_pct)}%`, 'warn'],
  ].map(([label, value, klass]) => `<article class="card"><div class="label">${label}</div><div class="value ${klass}">${value}</div></article>`).join('');
}
async function togglePause() {
  const data = await postJson('/api/control/toggle-pause');
  renderDashboard(data);
}
async function resetSimulation() {
  if (!confirm('Reset simulated balance, positions, trades, and ticks?')) return;
  const data = await postJson('/api/control/reset');
  renderDashboard(data);
}
async function runBacktest() {
  document.getElementById('backtestCards').innerHTML = '<article class="card"><div class="label">Status</div><div class="small-value">Running quick synthetic backtest...</div></article>';
  const data = await postJson('/api/backtest?limit=500');
  renderBacktest(data.report);
}
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


class BotifyHandler(BaseHTTPRequestHandler):
    """Small standard-library HTTP handler for local development."""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(PAGE)
        elif parsed.path == "/api/tick":
            self._send_json(tick_dashboard())
        elif parsed.path == "/api/state":
            self._send_json(snapshot_with_controls())
        elif parsed.path == "/api/control":
            self._send_json(control_state())
        else:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/control/toggle-pause":
            self._send_json(toggle_pause())
        elif parsed.path == "/api/control/reset":
            self._send_json(reset_simulation())
        elif parsed.path == "/api/backtest":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["500"])[0])
            self._send_json(run_quick_backtest(limit=limit))
        else:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def tick_dashboard() -> dict:
    """Advance one price tick unless paused and return dashboard state."""

    with state_lock:
        if not paused:
            price = price_feed.latest_price()
            engine.on_price(price)
        snapshot = _snapshot_unlocked()
    return snapshot
        return _snapshot_unlocked()


def control_state() -> dict:
    """Return pause/reset related state without the full trading snapshot."""

    with state_lock:
        state = {"paused": paused, "tick_count": engine.state.tick_count}
    return state
        return {"paused": paused, "tick_count": engine.state.tick_count}


def snapshot_with_controls() -> dict:
    """Return current dashboard state without advancing a tick."""

    with state_lock:
        snapshot = _snapshot_unlocked()
    return snapshot
        return _snapshot_unlocked()


def toggle_pause() -> dict:
    """Pause or resume automatic dashboard ticking."""

    global paused
    with state_lock:
        paused = not paused
        snapshot = _snapshot_unlocked()
    return snapshot
        return _snapshot_unlocked()


def reset_simulation() -> dict:
    """Reset simulated account state while keeping Botify BTC-only settings."""

    global engine, paused, last_backtest
    with state_lock:
        engine = GridEngine(CONFIG)
        paused = False
        last_backtest = None
        snapshot = _snapshot_unlocked()
    return snapshot
        return _snapshot_unlocked()


def run_quick_backtest(limit: int = 500) -> dict:
    """Run a deterministic synthetic backtest from the dashboard."""

    global last_backtest
    safe_limit = max(50, min(limit, 2000))
    report = run_backtest(
        synthetic_closes(limit=safe_limit),
        config=CONFIG,
        interval="5m",
        source="synthetic_dashboard",
    )
    with state_lock:
        last_backtest = _report_dict(report)
        payload = {"report": last_backtest, "state": _snapshot_unlocked()}
    return payload
        return {"report": last_backtest, "state": _snapshot_unlocked()}


def _report_dict(report: Any) -> dict:
    payload = report.__dict__.copy()
    if math.isinf(payload["profit_factor"]):
        payload["profit_factor"] = None
    return payload


def _snapshot_unlocked() -> dict:
    snapshot = engine.snapshot()
    snapshot["price_source"] = "fallback" if price_feed.using_fallback else "binance_public"
    snapshot["paused"] = paused
    snapshot["last_backtest"] = last_backtest
def _snapshot_with_source() -> dict:
    snapshot = engine.snapshot()
    snapshot["price_source"] = "fallback" if price_feed.using_fallback else "binance_public"
    return snapshot


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    server = ThreadingHTTPServer((host, port), BotifyHandler)
    print(f"Botify dashboard running at http://{host}:{port}")
    print("Press Ctrl+C to stop. No live orders are placed in this milestone.")
    server.serve_forever()


if __name__ == "__main__":
    run()
