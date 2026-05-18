"""Beginner-friendly BTCUSDT backtesting command for Botify.

Run from the repository root with the cross-platform launcher:

    python run.py backtest

The direct Unix/Git Bash form is still supported:

    PYTHONPATH=src python -m botify.backtest

The command tries to use Binance public 5-minute BTCUSDT candles. If Binance is
unavailable, it automatically falls back to deterministic synthetic prices so a
new user can still test the Botify engine locally.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .config import BotConfig
from .engine import GridEngine

BINANCE_KLINES_ENDPOINT = "https://api.binance.com/api/v3/klines"


@dataclass(frozen=True)
class BacktestReport:
    """Summary metrics from one Botify backtest run."""

    symbol: str
    interval: str
    source: str
    candles: int
    starting_balance: float
    ending_balance: float
    ending_equity: float
    total_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    closed_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    biggest_win: float
    biggest_loss: float
    open_positions: int
    trading_enabled: bool
    lock_reason: str

    def lines(self) -> list[str]:
        """Return a human-readable terminal report."""

        return [
            "Botify BTCUSDT Backtest Report",
            "=" * 34,
            f"Symbol:           {self.symbol}",
            f"Interval:         {self.interval}",
            f"Source:           {self.source}",
            f"Candles tested:   {self.candles}",
            f"Starting balance: ${self.starting_balance:,.2f}",
            f"Ending balance:   ${self.ending_balance:,.2f}",
            f"Ending equity:    ${self.ending_equity:,.2f}",
            f"Total return:     {self.total_return_pct:,.2f}%",
            f"Realized PnL:     ${self.realized_pnl:,.2f}",
            f"Unrealized PnL:   ${self.unrealized_pnl:,.2f}",
            f"Closed trades:    {self.closed_trades}",
            f"Win rate:         {self.win_rate:,.2f}%",
            f"Profit factor:    {format_profit_factor(self.profit_factor)}",
            f"Max drawdown:     {self.max_drawdown_pct:,.2f}%",
            f"Biggest win:      ${self.biggest_win:,.2f}",
            f"Biggest loss:     ${self.biggest_loss:,.2f}",
            f"Open positions:   {self.open_positions}",
            f"Trading enabled:  {self.trading_enabled}",
            f"Lock reason:      {self.lock_reason or 'none'}",
        ]


def fetch_binance_closes(symbol: str = "BTCUSDT", interval: str = "5m", limit: int = 1000) -> list[float]:
    """Fetch public Binance candle closes without API keys."""

    query = urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    with urlopen(f"{BINANCE_KLINES_ENDPOINT}?{query}", timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [float(candle[4]) for candle in payload]


def synthetic_closes(limit: int = 1000, start_price: float = 80_000.0) -> list[float]:
    """Create deterministic BTC-like prices for offline backtesting."""

    prices: list[float] = []
    for tick in range(1, limit + 1):
        cycle = math.sin(tick / 15) * 700
        slow_cycle = math.sin(tick / 97) * 2_200
        shock = math.sin(tick / 37) * math.cos(tick / 11) * 1_100
        drift = tick * 1.25
        price = max(1_000.0, start_price + cycle + slow_cycle + shock + drift)
        prices.append(price)
    return prices


def load_closes(source: str, symbol: str, interval: str, limit: int) -> tuple[list[float], str]:
    """Load closes from Binance, synthetic data, or Binance-with-fallback."""

    if source == "synthetic":
        return synthetic_closes(limit), "synthetic"

    try:
        return fetch_binance_closes(symbol=symbol, interval=interval, limit=limit), "binance_public"
    except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        if source == "binance":
            raise
        return synthetic_closes(limit), "synthetic_fallback"


def run_backtest(closes: Iterable[float], config: BotConfig | None = None, interval: str = "5m", source: str = "provided") -> BacktestReport:
    """Run Botify over a sequence of closing prices and return summary metrics."""

    config = config or BotConfig()
    engine = GridEngine(config)
    equity_curve: list[float] = []
    candle_count = 0

    for close in closes:
        candle_count += 1
        engine.on_price(close)
        snapshot = engine.snapshot()
        equity_curve.append(snapshot["equity"])

    if candle_count == 0:
        raise ValueError("Backtest needs at least one candle close.")

    snapshot = engine.snapshot()
    trades = engine.state.trades
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = math.inf if gross_profit and gross_loss == 0 else (gross_profit / gross_loss if gross_loss else 0.0)

    return BacktestReport(
        symbol=config.symbol,
        interval=interval,
        source=source,
        candles=candle_count,
        starting_balance=config.starting_balance,
        ending_balance=snapshot["balance"],
        ending_equity=snapshot["equity"],
        total_return_pct=(snapshot["equity"] - config.starting_balance) / config.starting_balance * 100,
        realized_pnl=snapshot["realized_pnl"],
        unrealized_pnl=snapshot["unrealized_pnl"],
        closed_trades=snapshot["closed_trades"],
        win_rate=snapshot["win_rate"],
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct(equity_curve),
        biggest_win=max(wins, default=0.0),
        biggest_loss=min(losses, default=0.0),
        open_positions=len(snapshot["positions"]),
        trading_enabled=snapshot["trading_enabled"],
        lock_reason=snapshot["lock_reason"],
    )


def max_drawdown_pct(equity_curve: Iterable[float]) -> float:
    """Return max peak-to-trough equity drawdown as a positive percentage."""

    peak = 0.0
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak:
            drawdown = (peak - equity) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown


def format_profit_factor(value: float) -> str:
    if math.isinf(value):
        return "infinite"
    return f"{value:,.2f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Botify BTCUSDT grid backtest.")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair. Milestone 2 only supports BTCUSDT.")
    parser.add_argument("--interval", default="5m", help="Binance candle interval, for example 1m, 5m, 15m, 1h.")
    parser.add_argument("--limit", type=int, default=1000, help="Number of candles to test. Binance public API max is usually 1000.")
    parser.add_argument(
        "--source",
        choices=("auto", "binance", "synthetic"),
        default="auto",
        help="Use Binance public candles, deterministic synthetic candles, or automatic fallback.",
    )
    parser.add_argument("--trading-bias", choices=("LONG", "SHORT", "NEUTRAL"), default="NEUTRAL", help="Choose long-only, short-only, or two-sided grid entries.")
    parser.add_argument("--grid-levels", type=int, default=12, help="Number of grid levels in the active range.")
    parser.add_argument("--range-pct", type=float, default=0.05, help="Base grid range as a decimal, for example 0.05 for 5%%.")
    parser.add_argument("--take-profit-grid-steps", type=int, default=3, help="Grid steps between entry and take-profit.")
    parser.add_argument("--stop-loss-pct", type=float, default=0.05, help="Stop loss from entry as a decimal.")
    parser.add_argument("--max-order-age-ticks", type=int, default=12, help="Cancel unfilled entry orders after this many candles.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BotConfig(
        symbol=args.symbol,
        trading_bias=args.trading_bias,
        grid_levels=args.grid_levels,
        range_pct=args.range_pct,
        take_profit_grid_steps=args.take_profit_grid_steps,
        stop_loss_pct=args.stop_loss_pct,
        max_order_age_ticks=args.max_order_age_ticks,
    )
    closes, source_used = load_closes(
        source=args.source,
        symbol=config.symbol,
        interval=args.interval,
        limit=args.limit,
    )
    report = run_backtest(closes, config=config, interval=args.interval, source=source_used)
    print("\n".join(report.lines()))


if __name__ == "__main__":
    main()
