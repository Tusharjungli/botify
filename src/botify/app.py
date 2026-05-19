"""Localhost dashboard for the Botify BTC grid simulator."""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

from .backtest import run_backtest, synthetic_closes
from .config import BotConfig
from .engine import GridEngine
from .market import BinancePublicPriceFeed, DeterministicPriceFeed, HybridPriceFeed

CONFIG = BotConfig()
engine = GridEngine(CONFIG)
price_feed = HybridPriceFeed(
    live_feed=BinancePublicPriceFeed(symbol="BTCUSDT"),
    fallback_feed=DeterministicPriceFeed(),
)
state_lock = Lock()
paused = False
last_backtest: dict | None = None
session_started_at = datetime.now(UTC)

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
    .good { color: #34d399; } .bad { color: #fb7185; } .warn { color: #fbbf24; }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 12px 14px; border-bottom: 1px solid #23304d; text-align: left; font-size: 14px; }
    th { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #1e293b; }
    .note { color: #a8b3c7; line-height: 1.5; max-width: 980px; }
    .review-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
    .review-list li { padding: 12px 14px; border: 1px solid #23304d; border-radius: 12px; background: #0f172a; color: #cbd5e1; }
    .status-line { min-height: 24px; color: #a8b3c7; }
    .chart-wrap { position: relative; height: 360px; }
    canvas { width: 100%; height: 100%; border-radius: 14px; background: #08111f; }
    .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; color: #a8b3c7; font-size: 13px; }
    .legend span::before { content: ''; display: inline-block; width: 18px; height: 3px; margin-right: 6px; vertical-align: middle; background: var(--c); }
  </style>
</head>
<body>
  <header>
    <h1>Botify — BTCUSDT Grid Simulator</h1>
    <p class="note">Simulation only: no private Binance keys and no live orders. Public BTC price is used when available; otherwise Botify falls back to a deterministic local feed.</p>
  </header>
  <main>
    <section class="panel">
      <h2>Controls</h2>
      <div class="toolbar">
        <button id="pauseButton" onclick="togglePause()">Pause</button>
        <button class="warning" onclick="resetSimulation()">Reset simulation</button>
        <button class="secondary" onclick="runBacktest()">Run quick synthetic backtest</button>
        <button class="secondary" onclick="cancelPaperOrders()">Cancel paper orders</button>
        <button class="warning" onclick="emergencyStop()">Emergency stop</button>
        <button class="secondary" onclick="exportTrades()">Export trades CSV</button>
      </div>
      <p class="status-line" id="statusLine">Loading dashboard state...</p>
    </section>
    <section class="cards" id="cards"></section>
    <section>
      <h2>Trade Diagnostics</h2>
      <div class="cards" id="diagnostics"></div>
    </section>
    <section class="panel">
      <h2>Run Review</h2>
      <ul class="review-list" id="reviewNotes"><li>Collecting run notes...</li></ul>
    </section>
    <section class="panel">
      <h2>BTC Price Chart</h2>
      <p class="note">Shows recent BTC prices, grid range, open entries, targets, and stops. This is still simulation-only.</p>
      <div class="chart-wrap"><canvas id="priceChart"></canvas></div>
      <div class="legend">
        <span style="--c:#38bdf8">Price</span>
        <span style="--c:#64748b">Grid range</span>
        <span style="--c:#fbbf24">Entry</span>
        <span style="--c:#34d399">Target</span>
        <span style="--c:#fb7185">Stop</span>
      </div>
    </section>
    <section>
      <h2>Risk Settings</h2>
      <div class="settings" id="settings"></div>
    </section>
    <section>
      <h2>Quick Backtest Result</h2>
      <div class="cards" id="backtestCards"><article class="card"><div class="label">Status</div><div class="small-value">Click “Run quick synthetic backtest”.</div></article></div>
    </section>
    <section>
      <h2>Open Paper Orders</h2>
      <table><thead><tr><th>ID</th><th>Side</th><th>Limit</th><th>Qty</th><th>Notional</th><th>Tag</th></tr></thead><tbody id="orders"></tbody></table>
    </section>
    <section>
      <h2>Recent Paper Fills</h2>
      <table><thead><tr><th>ID</th><th>Side</th><th>Limit</th><th>Fill</th><th>Qty</th><th>Filled</th></tr></thead><tbody id="fills"></tbody></table>
    </section>
    <section>
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
function formatElapsed(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds || 0)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}h ${String(m).padStart(2, '0')}m ${String(sec).padStart(2, '0')}s`;
}
function pnlClass(n) { return Number(n) >= 0 ? 'good' : 'bad'; }
function factorClass(n) { return n === null || Number(n) >= 1 ? 'good' : 'bad'; }
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
  const statusText = data.paused
    ? 'Paused: Botify is not advancing new price ticks. Click Resume to continue.'
    : 'Running: Botify advances one simulated tick every refresh. No live orders are placed.';
  const runtimeText = `Runtime: ${formatElapsed(data.uptime_seconds)} since ${new Date(data.session_started_at).toLocaleString()}.`;
  document.getElementById('statusLine').textContent = data.control_message ? `${data.control_message} ${statusText} ${runtimeText}` : `${statusText} ${runtimeText}`;
  document.getElementById('cards').innerHTML = [
    ['BTC Price', money(data.price), ''],
    ['Price Source', `<span class="pill">${data.price_source}</span>`, ''],
    ['Mode', `<span class="pill">${data.mode}</span>`, ''],
    ['Trend Strength', `${num(data.trend_strength_pct || 0)}%`, ''],
    ['Simulator', data.paused ? 'Paused' : 'Running', data.paused ? 'warn' : 'good'],
    ['Equity', money(data.equity), pnlClass(data.equity - data.config.starting_balance)],
    ['Balance', money(data.balance), ''],
    ['Realized PnL', money(data.realized_pnl), pnlClass(data.realized_pnl)],
    ['Unrealized PnL', money(data.unrealized_pnl), pnlClass(data.unrealized_pnl)],
    ['Daily PnL', `${num(data.daily_pnl_pct * 100)}%`, pnlClass(data.daily_pnl_pct)],
    ['Trading', data.trading_enabled ? 'Enabled' : 'Locked', data.trading_enabled ? 'good' : 'warn'],
    ['Win Rate', `${num(data.win_rate)}%`, ''],
    ['Closed Trades', data.closed_trades, ''],
    ['Runtime', formatElapsed(data.uptime_seconds), ''],
  ].map(([label, value, klass]) => `<article class="card"><div class="label">${label}</div><div class="value ${klass}">${value}</div></article>`).join('');

  renderDiagnostics(data.diagnostics);
  renderReviewNotes(data.review_notes);

  document.getElementById('settings').innerHTML = [
    ['Symbol', data.config.symbol],
    ['Starting Balance', money(data.config.starting_balance)],
    ['Trading Bias', data.config.trading_bias],
    ['Grid Levels', data.config.grid_levels],
    ['Range', `${num(data.config.range_pct * 100)}%`],
    ['Leverage', `${num(data.config.leverage)}x`],
    ['Order Risk', `${num(data.config.base_order_risk_pct * 100)}%`],
    ['Max Open Positions', data.config.max_open_positions],
    ['Max Open Orders', data.config.max_open_orders],
    ['Entry Offset', `${data.config.entry_grid_offset} grid step(s)`],
    ['Take Profit', `${data.config.take_profit_grid_steps} grid step(s)`],
    ['Order Max Age', `${data.config.max_order_age_ticks} tick(s)`],
    ['Daily Loss Lock', `${num(data.config.max_daily_loss_pct * 100)}%`],
    ['Profit Lock', `${num(data.config.daily_profit_lock_pct * 100)}%`],
    ['Stop Loss', `${num(data.config.stop_loss_pct * 100)}%`],
    ['Trailing Stop', `${num(data.config.trailing_stop_pct * 100)}%`],
    ['Min Grid Profit', `${num(data.config.min_grid_profit_pct * 100)}%`],
  ].map(([label, value]) => `<article class="card"><div class="label">${label}</div><div class="small-value">${value}</div></article>`).join('');

  document.getElementById('orders').innerHTML = data.open_orders.length ? data.open_orders.map(o => `
    <tr><td>${o.order_id}</td><td>${o.side}</td><td>${money(o.price)}</td><td>${num(o.quantity, 6)}</td><td>${money(o.notional)}</td><td>${o.tag}</td></tr>
  `).join('') : '<tr><td colspan="6">No open paper orders.</td></tr>';

  document.getElementById('fills').innerHTML = data.recent_fills.length ? data.recent_fills.map(o => `
    <tr><td>${o.order_id}</td><td>${o.side}</td><td>${money(o.price)}</td><td>${money(o.average_fill_price || o.price)}</td><td>${num(o.quantity, 6)}</td><td>${o.filled_at}</td></tr>
  `).join('') : '<tr><td colspan="6">No filled paper orders yet.</td></tr>';

  document.getElementById('positions').innerHTML = data.positions.length ? data.positions.map(p => `
    <tr><td>${p.side}</td><td>${money(p.entry_price)}</td><td>${money(p.target_price)}</td><td>${money(p.stop_price)}</td><td>${num(p.quantity, 6)}</td><td class="${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td></tr>
  `).join('') : '<tr><td colspan="6">No open positions yet.</td></tr>';

  document.getElementById('trades').innerHTML = data.trades.length ? data.trades.map(t => `
    <tr><td>${t.side}</td><td>${money(t.entry_price)}</td><td>${money(t.exit_price)}</td><td class="${pnlClass(t.pnl)}">${money(t.pnl)}</td><td>${t.reason}</td><td>${t.closed_at}</td></tr>
  `).join('') : '<tr><td colspan="6">No closed trades yet.</td></tr>';

  drawChart(data.chart);
  if (data.last_backtest) renderBacktest(data.last_backtest);
}
function renderDiagnostics(diagnostics) {
  if (!diagnostics) return;
  document.getElementById('diagnostics').innerHTML = [
    ['Open Exposure', money(diagnostics.open_exposure), ''],
    ['Open Positions', diagnostics.open_positions, ''],
    ['Long / Short', `${diagnostics.long_positions} / ${diagnostics.short_positions}`, ''],
    ['Gross Profit', money(diagnostics.gross_profit), 'good'],
    ['Gross Loss', money(-diagnostics.gross_loss), 'bad'],
    ['Profit Factor', diagnostics.profit_factor === null ? 'infinite' : num(diagnostics.profit_factor), factorClass(diagnostics.profit_factor)],
    ['Avg Win', money(diagnostics.average_win), pnlClass(diagnostics.average_win)],
    ['Avg Loss', money(diagnostics.average_loss), pnlClass(diagnostics.average_loss)],
    ['Expectancy', money(diagnostics.expectancy), pnlClass(diagnostics.expectancy)],
    ['Trend Flip Exits', diagnostics.trend_flip_exits, diagnostics.trend_flip_exits ? 'warn' : ''],
    ['Grid Width', `${num(diagnostics.grid_width_pct)}%`, ''],
    ['Nearest Target', diagnostics.nearest_target_distance_pct === null ? 'n/a' : `${num(diagnostics.nearest_target_distance_pct)}%`, ''],
  ].map(([label, value, klass]) => `<article class="card"><div class="label">${label}</div><div class="value ${klass}">${value}</div></article>`).join('');
}
function renderReviewNotes(notes) {
  const items = notes && notes.length ? notes : [{label: 'Waiting', message: 'Collecting enough ticks and trades for review.', level: ''}];
  document.getElementById('reviewNotes').innerHTML = items.map(note =>
    `<li><strong class="${note.level}">${note.label}</strong> — ${note.message}</li>`
  ).join('');
}
function drawChart(chart) {
  const canvas = document.getElementById('priceChart');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#08111f';
  ctx.fillRect(0, 0, width, height);
  if (!chart || !chart.prices || chart.prices.length < 2) {
    ctx.fillStyle = '#93a4bd';
    ctx.font = '16px Inter, Arial';
    ctx.fillText('Collecting price ticks for chart...', 18, 34);
    return;
  }
  const pad = {left: 72, right: 18, top: 20, bottom: 34};
  const markers = [];
  (chart.positions || []).forEach(p => {
    markers.push({price: p.entry_price, color: '#fbbf24', label: p.side});
    markers.push({price: p.target_price, color: '#34d399', label: 'target'});
    markers.push({price: p.stop_price, color: '#fb7185', label: 'stop'});
  });
  const gridValues = [chart.grid_lower, chart.grid_upper].filter(v => Number.isFinite(v));
  const values = chart.prices.concat(gridValues, markers.map(m => m.price));
  let min = Math.min(...values);
  let max = Math.max(...values);
  const buffer = Math.max((max - min) * 0.08, max * 0.0005);
  min -= buffer;
  max += buffer;
  const x = (i) => pad.left + (i / (chart.prices.length - 1)) * (width - pad.left - pad.right);
  const y = (price) => pad.top + ((max - price) / (max - min)) * (height - pad.top - pad.bottom);

  ctx.strokeStyle = '#172554';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = pad.top + i * (height - pad.top - pad.bottom) / 4;
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke();
    const price = max - i * (max - min) / 4;
    ctx.fillStyle = '#93a4bd'; ctx.font = '12px Inter, Arial';
    ctx.fillText(money(price), 8, yy + 4);
  }

  const labelSlots = [];
  function nextLabelY(yy) {
    let labelY = Math.max(pad.top + 10, Math.min(height - pad.bottom - 6, yy - 5));
    while (labelSlots.some(existing => Math.abs(existing - labelY) < 14)) {
      labelY = Math.min(height - pad.bottom - 6, labelY + 14);
      if (labelY >= height - pad.bottom - 6) break;
    }
    labelSlots.push(labelY);
    return labelY;
  }
  function horizontal(price, color, label, dash = [], stackLabel = false) {
    if (!Number.isFinite(price)) return;
    const yy = y(price);
    ctx.save(); ctx.setLineDash(dash); ctx.strokeStyle = color; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right, yy); ctx.stroke(); ctx.restore();
    const labelY = stackLabel ? nextLabelY(yy) : yy - 5;
    ctx.font = '12px Inter, Arial';
    ctx.fillStyle = '#08111fcc';
    ctx.fillRect(pad.left + 4, labelY - 12, ctx.measureText(label).width + 8, 14);
    ctx.fillStyle = color; ctx.fillText(label, pad.left + 8, labelY);
  }
  horizontal(chart.grid_lower, '#64748b', 'grid low', [6, 6]);
  horizontal(chart.grid_upper, '#64748b', 'grid high', [6, 6]);
  markers.forEach(m => horizontal(m.price, m.color, m.label, [3, 5], true));

  const grad = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  grad.addColorStop(0, '#38bdf844'); grad.addColorStop(1, '#38bdf800');
  ctx.beginPath();
  chart.prices.forEach((price, i) => { i ? ctx.lineTo(x(i), y(price)) : ctx.moveTo(x(i), y(price)); });
  ctx.lineTo(x(chart.prices.length - 1), height - pad.bottom);
  ctx.lineTo(x(0), height - pad.bottom);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

  ctx.beginPath();
  chart.prices.forEach((price, i) => { i ? ctx.lineTo(x(i), y(price)) : ctx.moveTo(x(i), y(price)); });
  ctx.strokeStyle = '#38bdf8'; ctx.lineWidth = 2.5; ctx.stroke();

  ctx.fillStyle = '#e2e8f0'; ctx.font = '13px Inter, Arial';
  ctx.fillText(`${chart.prices.length} ticks • Last ${money(chart.last_price)}`, pad.left, height - 10);
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
async function cancelPaperOrders() {
  if (!confirm('Cancel all open paper orders? Open positions are unchanged.')) return;
  const data = await postJson('/api/control/cancel-orders');
  renderDashboard(data);
}
async function emergencyStop() {
  if (!confirm('Emergency stop will cancel open paper orders and disable new entries. Continue?')) return;
  const data = await postJson('/api/control/emergency-stop');
  renderDashboard(data);
}
function exportTrades() {
  window.location.href = '/api/trades.csv';
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
        elif parsed.path == "/api/trades.csv":
            self._send_csv(trades_csv())
        else:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/control/toggle-pause":
            self._send_json(toggle_pause())
        elif parsed.path == "/api/control/reset":
            self._send_json(reset_simulation())
        elif parsed.path == "/api/control/cancel-orders":
            self._send_json(cancel_paper_orders())
        elif parsed.path == "/api/control/emergency-stop":
            self._send_json(emergency_stop())
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
        self._safe_write(encoded)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self._safe_write(encoded)

    def _send_csv(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="botify_trades.csv"')
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self._safe_write(encoded)

    def _safe_write(self, encoded: bytes) -> None:
        try:
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


def tick_dashboard() -> dict:
    """Advance one price tick unless paused and return dashboard state."""

    with state_lock:
        if not paused:
            price = price_feed.latest_price()
            engine.on_price(price)
        snapshot = _snapshot_unlocked()
    return snapshot


def control_state() -> dict:
    """Return pause/reset related state without the full trading snapshot."""

    with state_lock:
        state = {"paused": paused, "tick_count": engine.state.tick_count, "session_started_at": session_started_at.isoformat(), "uptime_seconds": _uptime_seconds()}
    return state


def snapshot_with_controls() -> dict:
    """Return current dashboard state without advancing a tick."""

    with state_lock:
        snapshot = _snapshot_unlocked()
    return snapshot


def toggle_pause() -> dict:
    """Pause or resume automatic dashboard ticking."""

    global paused
    with state_lock:
        paused = not paused
        snapshot = _snapshot_unlocked()
    return snapshot


def reset_simulation() -> dict:
    """Reset simulated account state while keeping Botify BTC-only settings."""

    global engine, paused, last_backtest, session_started_at
    with state_lock:
        engine = GridEngine(CONFIG)
        paused = False
        last_backtest = None
        session_started_at = datetime.now(UTC)
        snapshot = _snapshot_unlocked()
    return snapshot


def cancel_paper_orders() -> dict:
    """Cancel all open local paper orders without closing positions."""

    with state_lock:
        canceled = engine.cancel_open_orders()
        snapshot = _snapshot_unlocked()
    snapshot["control_message"] = f"Canceled {canceled} open paper order(s)."
    return snapshot


def emergency_stop() -> dict:
    """Cancel open paper orders and disable new simulated entries."""

    with state_lock:
        canceled = engine.emergency_stop()
        snapshot = _snapshot_unlocked()
    snapshot["control_message"] = f"Emergency stop active. Canceled {canceled} open paper order(s)."
    return snapshot


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
    snapshot["chart"] = _chart_payload(snapshot)
    snapshot["diagnostics"] = _diagnostics_payload(snapshot)
    snapshot["review_notes"] = _review_notes_payload(snapshot, snapshot["diagnostics"])
    snapshot["session_started_at"] = session_started_at.isoformat()
    snapshot["uptime_seconds"] = _uptime_seconds()
    return snapshot



def _uptime_seconds() -> int:
    return max(0, int((datetime.now(UTC) - session_started_at).total_seconds()))

def _diagnostics_payload(snapshot: dict) -> dict:
    trades = engine.state.trades
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        math.inf
        if gross_profit and gross_loss == 0
        else (gross_profit / gross_loss if gross_loss else 0.0)
    )
    positions = snapshot.get("positions", [])
    price = snapshot.get("price", 0.0)
    grid = snapshot.get("grid", [])
    target_distances = [
        abs(position["target_price"] - price) / price * 100
        for position in positions
        if price
    ]
    closed_trades = len(trades)
    expectancy = sum(trade.pnl for trade in trades) / closed_trades if closed_trades else 0.0
    return {
        "open_exposure": sum(position["notional"] for position in positions),
        "open_positions": len(positions),
        "long_positions": sum(1 for position in positions if position["side"] == "LONG"),
        "short_positions": sum(1 for position in positions if position["side"] == "SHORT"),
        "average_win": gross_profit / len(wins) if wins else 0.0,
        "average_loss": sum(losses) / len(losses) if losses else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": None if math.isinf(profit_factor) else profit_factor,
        "expectancy": expectancy,
        "trend_flip_exits": sum(1 for trade in trades if trade.reason == "trend_flip"),
        "grid_width_pct": ((grid[-1] - grid[0]) / price * 100) if grid and price else 0.0,
        "nearest_target_distance_pct": min(target_distances) if target_distances else None,
    }


def _review_notes_payload(snapshot: dict, diagnostics: dict) -> list[dict[str, str]]:
    notes = []
    closed_trades = snapshot.get("closed_trades", 0)
    profit_factor = diagnostics.get("profit_factor")
    trend_flip_exits = diagnostics.get("trend_flip_exits", 0)
    open_exposure = diagnostics.get("open_exposure", 0.0)
    equity = snapshot.get("equity", 0.0)
    exposure_pct = (open_exposure / equity * 100) if equity else 0.0

    if closed_trades < 10:
        notes.append({
            "label": "Small sample",
            "message": "Keep the simulator running before judging win rate or profit factor.",
            "level": "warn",
        })
    elif profit_factor is None or profit_factor >= 1:
        notes.append({
            "label": "Positive edge",
            "message": "Closed trades are profitable so far, but continue monitoring drawdown.",
            "level": "good",
        })
    else:
        notes.append({
            "label": "Needs tuning",
            "message": "Closed-trade losses are larger than wins in this sample.",
            "level": "bad",
        })

    if trend_flip_exits >= max(2, closed_trades * 0.4):
        notes.append({
            "label": "Trend flips active",
            "message": "Frequent trend-flip exits may mean the grid is too tight for the current market.",
            "level": "warn",
        })

    notes.append({
        "label": "Exposure",
        "message": f"Open simulated notional is {exposure_pct:.1f}% of current equity.",
        "level": "warn" if exposure_pct > 20 else "good",
    })

    if not snapshot.get("trading_enabled", True):
        notes.append({
            "label": "Trading locked",
            "message": "A configured risk lock is preventing new simulated entries.",
            "level": "bad",
        })

    return notes


def trades_csv() -> str:
    with state_lock:
        trades = list(engine.state.trades)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "side",
        "entry_price",
        "exit_price",
        "quantity",
        "pnl",
        "reason",
        "opened_at",
        "closed_at",
    ])
    for trade in trades:
        writer.writerow([
            trade.side,
            trade.entry_price,
            trade.exit_price,
            trade.quantity,
            trade.pnl,
            trade.reason,
            trade.opened_at,
            trade.closed_at,
        ])
    return output.getvalue()


def _chart_payload(snapshot: dict) -> dict:
    grid = snapshot.get("grid", [])
    prices = engine.state.prices[-120:]
    return {
        "prices": prices,
        "last_price": snapshot.get("price", 0.0),
        "grid_lower": grid[0] if grid else None,
        "grid_upper": grid[-1] if grid else None,
        "positions": snapshot.get("positions", []),
    }


def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    server = ThreadingHTTPServer((host, port), BotifyHandler)
    print(f"Botify dashboard running at http://{host}:{port}")
    print("Press Ctrl+C to stop. No live orders are placed in this milestone.")
    server.serve_forever()


if __name__ == "__main__":
    run()
