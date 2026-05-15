"""Headless paper-session collector for Botify.

This command runs the same local simulator without requiring the browser to stay
open. It writes session snapshots and closed trades to disk so overnight paper
runs are not lost when the dashboard is reset or the terminal closes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .backtest import format_profit_factor, max_drawdown_pct
from .config import BotConfig
from .engine import GridEngine, Trade
from .market import BinancePublicPriceFeed, DeterministicPriceFeed, HybridPriceFeed, PriceFeed


@dataclass(frozen=True)
class PaperSessionReport:
    """Summary of one headless paper run."""

    symbol: str
    source: str
    ticks: int
    target_closed_trades: int
    starting_balance: float
    ending_balance: float
    ending_equity: float
    total_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    closed_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    biggest_win: float
    biggest_loss: float
    open_positions: int
    open_orders: int
    trading_enabled: bool
    lock_reason: str
    output_dir: str
    recommendation: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        if math.isinf(payload["profit_factor"]):
            payload["profit_factor"] = None
            payload["profit_factor_label"] = "infinite"
        else:
            payload["profit_factor_label"] = format_profit_factor(self.profit_factor)
        return payload

    def lines(self) -> list[str]:
        return [
            "Botify BTCUSDT Paper Session Report",
            "=" * 36,
            f"Symbol:               {self.symbol}",
            f"Source:               {self.source}",
            f"Ticks collected:      {self.ticks}",
            f"Target closed trades: {self.target_closed_trades}",
            f"Starting balance:     ${self.starting_balance:,.2f}",
            f"Ending balance:       ${self.ending_balance:,.2f}",
            f"Ending equity:        ${self.ending_equity:,.2f}",
            f"Total return:         {self.total_return_pct:,.2f}%",
            f"Realized PnL:         ${self.realized_pnl:,.2f}",
            f"Unrealized PnL:       ${self.unrealized_pnl:,.2f}",
            f"Closed trades:        {self.closed_trades}",
            f"Win rate:             {self.win_rate:,.2f}%",
            f"Profit factor:        {format_profit_factor(self.profit_factor)}",
            f"Expectancy:           ${self.expectancy:,.2f}",
            f"Max drawdown:         {self.max_drawdown_pct:,.2f}%",
            f"Biggest win:          ${self.biggest_win:,.2f}",
            f"Biggest loss:         ${self.biggest_loss:,.2f}",
            f"Open positions:       {self.open_positions}",
            f"Open orders:          {self.open_orders}",
            f"Trading enabled:      {self.trading_enabled}",
            f"Lock reason:          {self.lock_reason or 'none'}",
            f"Output dir:           {self.output_dir}",
            f"Recommendation:       {self.recommendation}",
        ]


def run_paper_session(
    *,
    ticks: int = 2_000,
    target_closed_trades: int = 30,
    source: str = "auto",
    sleep_seconds: float = 0.0,
    save_every: int = 50,
    output_dir: Path | str = "data/paper_sessions",
    config: BotConfig | None = None,
) -> PaperSessionReport:
    """Run a paper session and persist report, latest snapshot, and trades."""

    if ticks < 1:
        raise ValueError("ticks must be at least 1")
    if target_closed_trades < 1:
        raise ValueError("target_closed_trades must be at least 1")
    if save_every < 1:
        raise ValueError("save_every must be at least 1")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative")

    config = config or BotConfig()
    engine = GridEngine(config)
    feed = _build_feed(source=source, symbol=config.symbol)
    session_dir = _session_dir(output_dir)
    equity_curve: list[float] = []
    source_used = source
    snapshot: dict = {}

    for tick in range(1, ticks + 1):
        price = feed.latest_price()
        engine.on_price(price)
        snapshot = engine.snapshot()
        equity_curve.append(snapshot["equity"])
        source_used = _source_used(source, feed)

        if tick % save_every == 0 or snapshot["closed_trades"] >= target_closed_trades:
            _write_snapshot(session_dir, snapshot, source_used=source_used)
            _write_trades_csv(session_dir, engine.state.trades)

        if snapshot["closed_trades"] >= target_closed_trades:
            break
        if sleep_seconds:
            time.sleep(sleep_seconds)

    if not snapshot:
        snapshot = engine.snapshot()
    report = _build_report(
        config=config,
        snapshot=snapshot,
        trades=engine.state.trades,
        equity_curve=equity_curve,
        source_used=source_used,
        target_closed_trades=target_closed_trades,
        session_dir=session_dir,
    )
    _write_snapshot(session_dir, snapshot, source_used=source_used)
    _write_trades_csv(session_dir, engine.state.trades)
    _write_report(session_dir, report)
    return report


def build_config_from_args(args: argparse.Namespace) -> BotConfig:
    """Build BotConfig with optional strategy overrides from the CLI."""

    config = BotConfig()
    overrides = {
        "range_pct": args.range_pct,
        "passive_entry_offset_steps": args.entry_offset,
        "min_grid_profit_pct": args.min_grid_profit_pct,
        "trailing_stop_pct": args.trailing_stop_pct,
        "stop_loss_pct": args.stop_loss_pct,
        "trend_flip_min_loss_pct": args.trend_flip_min_loss_pct,
    }
    applied = {name: value for name, value in overrides.items() if value is not None}
    if applied:
        config = replace(config, **applied)
    config.validate()
    return config


def _build_feed(*, source: str, symbol: str) -> PriceFeed:
    if source == "synthetic":
        return DeterministicPriceFeed(start_price=80_000)
    if source == "binance":
        return BinancePublicPriceFeed(symbol=symbol)
    if source == "auto":
        return HybridPriceFeed(
            live_feed=BinancePublicPriceFeed(symbol=symbol),
            fallback_feed=DeterministicPriceFeed(start_price=80_000),
        )
    raise ValueError("source must be auto, binance, or synthetic")


def _source_used(requested_source: str, feed: PriceFeed) -> str:
    if requested_source == "auto" and isinstance(feed, HybridPriceFeed):
        return "synthetic_fallback" if feed.using_fallback else "binance_public"
    if requested_source == "binance":
        return "binance_public"
    return requested_source


def _session_dir(output_dir: Path | str) -> Path:
    root = Path(output_dir)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = root / f"paper-{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_report(
    *,
    config: BotConfig,
    snapshot: dict,
    trades: list[Trade],
    equity_curve: Iterable[float],
    source_used: str,
    target_closed_trades: int,
    session_dir: Path,
) -> PaperSessionReport:
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = math.inf if gross_profit and gross_loss == 0 else (gross_profit / gross_loss if gross_loss else 0.0)
    closed_trades = len(trades)
    expectancy = sum(trade.pnl for trade in trades) / closed_trades if closed_trades else 0.0
    recommendation = _recommendation(
        closed_trades=closed_trades,
        target_closed_trades=target_closed_trades,
        ending_equity=snapshot["equity"],
        starting_balance=config.starting_balance,
        profit_factor=profit_factor,
        expectancy=expectancy,
        lock_reason=snapshot.get("lock_reason", ""),
    )
    return PaperSessionReport(
        symbol=config.symbol,
        source=source_used,
        ticks=snapshot["tick_count"],
        target_closed_trades=target_closed_trades,
        starting_balance=config.starting_balance,
        ending_balance=snapshot["balance"],
        ending_equity=snapshot["equity"],
        total_return_pct=(snapshot["equity"] - config.starting_balance) / config.starting_balance * 100,
        realized_pnl=snapshot["realized_pnl"],
        unrealized_pnl=snapshot["unrealized_pnl"],
        closed_trades=closed_trades,
        win_rate=snapshot["win_rate"],
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown_pct=max_drawdown_pct(equity_curve),
        biggest_win=max(wins, default=0.0),
        biggest_loss=min(losses, default=0.0),
        open_positions=len(snapshot["positions"]),
        open_orders=len(snapshot["open_orders"]),
        trading_enabled=snapshot["trading_enabled"],
        lock_reason=snapshot.get("lock_reason", ""),
        output_dir=str(session_dir),
        recommendation=recommendation,
    )


def _recommendation(
    *,
    closed_trades: int,
    target_closed_trades: int,
    ending_equity: float,
    starting_balance: float,
    profit_factor: float,
    expectancy: float,
    lock_reason: str,
) -> str:
    if lock_reason:
        return "NOT_READY: risk/manual lock is active; investigate before testnet."
    if closed_trades < target_closed_trades:
        return f"NOT_READY: collect at least {target_closed_trades} closed paper trades before judging edge."
    if ending_equity <= starting_balance:
        return "NOT_READY: paper equity is not above starting balance."
    if profit_factor < 1.05 or expectancy <= 0:
        return "NOT_READY: paper edge is too weak; tune/backtest before testnet."
    return "READY_FOR_TESTNET_REVIEW: try read-only/testnet next, not live funds."


def _write_snapshot(session_dir: Path, snapshot: dict, *, source_used: str) -> None:
    payload = snapshot | {"source": source_used, "saved_at": datetime.now(UTC).isoformat(timespec="seconds")}
    (session_dir / "latest_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_report(session_dir: Path, report: PaperSessionReport) -> None:
    (session_dir / "report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def _write_trades_csv(session_dir: Path, trades: list[Trade]) -> None:
    with (session_dir / "trades.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a headless Botify BTCUSDT paper-data collection session.")
    parser.add_argument("--ticks", type=int, default=2_000, help="Maximum price ticks to collect.")
    parser.add_argument("--target-closed-trades", type=int, default=30, help="Stop once this many trades have closed.")
    parser.add_argument(
        "--source",
        choices=("auto", "binance", "synthetic"),
        default="auto",
        help="Use Binance public ticker, deterministic synthetic data, or automatic fallback.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Delay between ticks. Use 3 for dashboard-like polling.")
    parser.add_argument("--save-every", type=int, default=50, help="Persist snapshot/trades every N ticks.")
    parser.add_argument("--output-dir", default="data/paper_sessions", help="Directory for session folders.")
    parser.add_argument("--range-pct", type=float, default=None, help="Override grid range as a decimal, e.g. 0.035 for 3.5%%.")
    parser.add_argument("--entry-offset", type=float, default=None, help="Override passive_entry_offset_steps from optimizer output.")
    parser.add_argument("--min-grid-profit-pct", type=float, default=None, help="Override min grid profit as a decimal, e.g. 0.0015 for 0.15%%.")
    parser.add_argument("--trailing-stop-pct", type=float, default=None, help="Override trailing stop as a decimal, e.g. 0.004 for 0.4%%.")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="Override stop loss as a decimal, e.g. 0.01 for 1%%.")
    parser.add_argument("--trend-flip-min-loss-pct", type=float, default=None, help="Override trend flip min loss as a decimal, e.g. 0.006 for 0.6%%.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_paper_session(
        ticks=args.ticks,
        target_closed_trades=args.target_closed_trades,
        source=args.source,
        sleep_seconds=args.sleep_seconds,
        save_every=args.save_every,
        output_dir=args.output_dir,
        config=build_config_from_args(args),
    )
    print("\n".join(report.lines()))


if __name__ == "__main__":
    main()
