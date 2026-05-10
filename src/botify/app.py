"""Localhost dashboard for the Botify BTC grid simulator."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import BotConfig
from .engine import GridEngine
from .market import BinancePublicPriceFeed, DeterministicPriceFeed, HybridPriceFeed

engine = GridEngine(BotConfig())
price_feed = HybridPriceFeed(
    live_feed=BinancePublicPriceFeed(symbol="BTCUSDT"),
    fallback_feed=DeterministicPriceFeed(),
)

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
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
    .card, table { background: #111827; border: 1px solid #23304d; border-radius: 16px; box-shadow: 0 16px 32px #0004; }
    .card { padding: 16px; }
    .label { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { margin-top: 8px; font-size: 24px; font-weight: 800; }
    .good { color: #34d399; } .bad { color: #fb7185; } .warn { color: #fbbf24; }
    table { width: 100%; border-collapse: collapse; overflow: hidden; }
    th, td { padding: 12px 14px; border-bottom: 1px solid #23304d; text-align: left; font-size: 14px; }
    th { color: #93a4bd; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #1e293b; }
    .note { color: #a8b3c7; line-height: 1.5; max-width: 980px; }
  </style>
</head>
<body>
  <header>
    <h1>Botify — BTCUSDT Grid Simulator</h1>
    <p class="note">Simulation only: no private Binance keys and no live orders. Public BTC price is used when available; otherwise Botify falls back to a deterministic local feed.</p>
  </header>
  <main>
    <section class="cards" id="cards"></section>
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
function pnlClass(n) { return Number(n) >= 0 ? 'good' : 'bad'; }
async function refresh() {
  const response = await fetch('/api/tick');
  const data = await response.json();
  document.getElementById('cards').innerHTML = [
    ['BTC Price', money(data.price), ''],
    ['Price Source', `<span class="pill">${data.price_source}</span>`, ''],
    ['Mode', `<span class="pill">${data.mode}</span>`, ''],
    ['Equity', money(data.equity), pnlClass(data.equity - data.config.starting_balance)],
    ['Balance', money(data.balance), ''],
    ['Realized PnL', money(data.realized_pnl), pnlClass(data.realized_pnl)],
    ['Unrealized PnL', money(data.unrealized_pnl), pnlClass(data.unrealized_pnl)],
    ['Daily PnL', `${num(data.daily_pnl_pct * 100)}%`, pnlClass(data.daily_pnl_pct)],
    ['Trading', data.trading_enabled ? 'Enabled' : 'Locked', data.trading_enabled ? 'good' : 'warn'],
    ['Win Rate', `${num(data.win_rate)}%`, ''],
    ['Closed Trades', data.closed_trades, ''],
  ].map(([label, value, klass]) => `<article class="card"><div class="label">${label}</div><div class="value ${klass}">${value}</div></article>`).join('');

  document.getElementById('positions').innerHTML = data.positions.length ? data.positions.map(p => `
    <tr><td>${p.side}</td><td>${money(p.entry_price)}</td><td>${money(p.target_price)}</td><td>${money(p.stop_price)}</td><td>${num(p.quantity, 6)}</td><td class="${pnlClass(p.unrealized_pnl)}">${money(p.unrealized_pnl)}</td></tr>
  `).join('') : '<tr><td colspan="6">No open positions yet.</td></tr>';

  document.getElementById('trades').innerHTML = data.trades.length ? data.trades.map(t => `
    <tr><td>${t.side}</td><td>${money(t.entry_price)}</td><td>${money(t.exit_price)}</td><td class="${pnlClass(t.pnl)}">${money(t.pnl)}</td><td>${t.reason}</td><td>${t.closed_at}</td></tr>
  `).join('') : '<tr><td colspan="6">No closed trades yet.</td></tr>';
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
        if self.path == "/":
            self._send_html(PAGE)
        elif self.path == "/api/tick":
            price = price_feed.latest_price()
            engine.on_price(price)
            snapshot = _snapshot_with_source()
            self._send_json(snapshot)
        elif self.path == "/api/state":
            self._send_json(_snapshot_with_source())
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
