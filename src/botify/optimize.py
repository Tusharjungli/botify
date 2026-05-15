"""Small parameter sweep for Botify backtest tuning.

Use this before testnet/live decisions. It runs conservative strategy variants over
the same price series and ranks them by a safety-first score, not just return.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

from .backtest import BacktestReport, format_profit_factor, load_closes, run_backtest
from .config import BotConfig


@dataclass(frozen=True)
class SweepResult:
    """One configuration variant and its backtest result."""

    rank: int
    score: float
    recommendation: str
    range_pct: float
    passive_entry_offset_steps: float
    min_grid_profit_pct: float
    trailing_stop_pct: float
    stop_loss_pct: float
    closed_trades: int
    total_return_pct: float
    ending_equity: float
    profit_factor: float
    win_rate: float
    max_drawdown_pct: float
    realized_pnl: float
    biggest_loss: float

    def to_dict(self) -> dict:
        payload = asdict(self)
        if math.isinf(payload["profit_factor"]):
            payload["profit_factor"] = None
            payload["profit_factor_label"] = "infinite"
        else:
            payload["profit_factor_label"] = format_profit_factor(self.profit_factor)
        return payload


@dataclass(frozen=True)
class SweepReport:
    """Ranked sweep report with source metadata."""

    source: str
    interval: str
    candles: int
    variants_tested: int
    results: list[SweepResult]

    @property
    def candidate_count(self) -> int:
        return sum(1 for result in self.results if result.recommendation == "CANDIDATE_FOR_PAPER_TEST")

    def lines(self, limit: int = 10) -> list[str]:
        rows = [
            "Botify Parameter Sweep Report",
            "=" * 30,
            f"Source:          {self.source}",
            f"Interval:        {self.interval}",
            f"Candles:         {self.candles}",
            f"Variants tested: {self.variants_tested}",
            f"Candidates:      {self.candidate_count}",
            "",
            "Top variants:",
        ]
        for result in self.results[:limit]:
            rows.append(
                "#{} score={:.2f} return={:.2f}% PF={} trades={} DD={:.2f}% "
                "range={:.2f}% offset={:.2f} min_profit={:.2f}% trail={:.2f}% stop={:.2f}% {}".format(
                    result.rank,
                    result.score,
                    result.total_return_pct,
                    format_profit_factor(result.profit_factor),
                    result.closed_trades,
                    result.max_drawdown_pct,
                    result.range_pct * 100,
                    result.passive_entry_offset_steps,
                    result.min_grid_profit_pct * 100,
                    result.trailing_stop_pct * 100,
                    result.stop_loss_pct * 100,
                    result.recommendation,
                )
            )
        if self.candidate_count == 0:
            rows.extend([
                "",
                "No candidate passed the gates. Do not move to testnet/live yet.",
                "Next: run a longer Binance sweep, for example --limit 3000, then paper-test only a variant that shows positive equity and PF >= 1.05.",
            ])
        return rows

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "interval": self.interval,
            "candles": self.candles,
            "variants_tested": self.variants_tested,
            "candidate_count": self.candidate_count,
            "results": [result.to_dict() for result in self.results],
        }


def run_parameter_sweep(
    closes: Iterable[float],
    *,
    base_config: BotConfig | None = None,
    interval: str = "5m",
    source: str = "provided",
) -> SweepReport:
    """Run a conservative grid of config variants and rank by safety-first score."""

    price_series = list(closes)
    if not price_series:
        raise ValueError("Parameter sweep needs at least one close.")

    base = base_config or BotConfig()
    results: list[SweepResult] = []
    variants = list(_config_variants(base))
    for config in variants:
        report = run_backtest(price_series, config=config, interval=interval, source=source)
        score = _score(report)
        results.append(_result_from_report(report=report, config=config, score=score, rank=0))

    ranked = sorted(results, key=lambda result: result.score, reverse=True)
    ranked = [replace(result, rank=index + 1) for index, result in enumerate(ranked)]
    return SweepReport(
        source=source,
        interval=interval,
        candles=len(price_series),
        variants_tested=len(variants),
        results=ranked,
    )


def _config_variants(base: BotConfig) -> Iterable[BotConfig]:
    range_pcts = (0.025, 0.035, 0.05)
    entry_offsets = (0.25, 0.35, 0.5)
    min_profit_pcts = (0.0015, 0.0025)
    trailing_pcts = (0.004, 0.006)
    stop_loss_pcts = (0.01, 0.012, 0.016)
    for range_pct in range_pcts:
        for entry_offset in entry_offsets:
            for min_profit_pct in min_profit_pcts:
                for trailing_pct in trailing_pcts:
                    for stop_loss_pct in stop_loss_pcts:
                        yield replace(
                            base,
                            range_pct=range_pct,
                            passive_entry_offset_steps=entry_offset,
                            min_grid_profit_pct=min_profit_pct,
                            trailing_stop_pct=trailing_pct,
                            stop_loss_pct=stop_loss_pct,
                        )


def _score(report: BacktestReport) -> float:
    if report.closed_trades < 10:
        trade_penalty = (10 - report.closed_trades) * 5
    else:
        trade_penalty = 0
    pf_score = min(report.profit_factor if not math.isinf(report.profit_factor) else 3.0, 3.0) * 20
    return_score = report.total_return_pct * 10
    drawdown_penalty = report.max_drawdown_pct * 4
    loss_penalty = abs(report.biggest_loss) / 2
    return pf_score + return_score + report.win_rate / 5 - drawdown_penalty - loss_penalty - trade_penalty


def _result_from_report(*, report: BacktestReport, config: BotConfig, score: float, rank: int) -> SweepResult:
    return SweepResult(
        rank=rank,
        score=score,
        recommendation=_recommendation(report),
        range_pct=config.range_pct,
        passive_entry_offset_steps=config.passive_entry_offset_steps,
        min_grid_profit_pct=config.min_grid_profit_pct,
        trailing_stop_pct=config.trailing_stop_pct,
        stop_loss_pct=config.stop_loss_pct,
        closed_trades=report.closed_trades,
        total_return_pct=report.total_return_pct,
        ending_equity=report.ending_equity,
        profit_factor=report.profit_factor,
        win_rate=report.win_rate,
        max_drawdown_pct=report.max_drawdown_pct,
        realized_pnl=report.realized_pnl,
        biggest_loss=report.biggest_loss,
    )


def _recommendation(report: BacktestReport) -> str:
    if report.closed_trades < 30:
        return "NEEDS_MORE_TRADES"
    if report.ending_equity <= report.starting_balance:
        return "REJECT_EQUITY_BELOW_START"
    if report.profit_factor < 1.05:
        return "REJECT_WEAK_PROFIT_FACTOR"
    return "CANDIDATE_FOR_PAPER_TEST"


def write_sweep_outputs(report: SweepReport, output_dir: Path | str) -> None:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "sweep_report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    with (path / "sweep_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(report.results[0].to_dict().keys()) if report.results else [])
        if report.results:
            writer.writeheader()
            for result in report.results:
                writer.writerow(result.to_dict())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Botify parameter sweep before testnet/live decisions.")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair. Botify currently supports BTCUSDT.")
    parser.add_argument("--interval", default="5m", help="Binance candle interval, for example 1m, 5m, 15m, 1h.")
    parser.add_argument("--limit", type=int, default=1000, help="Number of closes to test. Binance requests above 1000 are paginated.")
    parser.add_argument(
        "--source",
        choices=("auto", "binance", "synthetic"),
        default="auto",
        help="Use Binance public candles, deterministic synthetic candles, or automatic fallback.",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of ranked variants to print.")
    parser.add_argument("--output-dir", default="data/optimization", help="Directory for sweep JSON/CSV outputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = BotConfig(symbol=args.symbol)
    closes, source_used = load_closes(args.source, base.symbol, args.interval, args.limit)
    report = run_parameter_sweep(closes, base_config=base, interval=args.interval, source=source_used)
    write_sweep_outputs(report, args.output_dir)
    print("\n".join(report.lines(limit=args.top)))
    print(f"\nSaved sweep_report.json and sweep_results.csv to {args.output_dir}")


if __name__ == "__main__":
    main()
