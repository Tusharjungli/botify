"""Configuration defaults for Botify's BTC-only grid simulator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    """Risk and strategy settings for the first Botify milestone.

    These defaults intentionally run in simulation mode only. They are designed
    for BTCUSDT so we can validate the engine before adding authenticated
    Binance Futures order placement.
    """

    symbol: str = "BTCUSDT"
    starting_balance: float = 10_000.0
    grid_levels: int = 24
    range_pct: float = 0.035
    leverage: float = 2.0
    base_order_risk_pct: float = 0.0125
    max_open_positions: int = 6
    max_daily_loss_pct: float = 0.025
    daily_profit_lock_pct: float = 0.035
    stop_loss_pct: float = 0.012
    take_profit_grid_steps: int = 1
    maker_fee_pct: float = 0.0002
    taker_fee_pct: float = 0.0005
    trailing_stop_pct: float = 0.004
    min_grid_profit_pct: float = 0.0015
    cooldown_ticks: int = 2
    ema_fast: int = 9
    ema_slow: int = 21
    trend_strength_threshold: float = 0.00035

    def validate(self) -> None:
        if self.symbol != "BTCUSDT":
            raise ValueError("Botify milestone 1 is BTC-only. Use symbol='BTCUSDT'.")
        if self.grid_levels < 4:
            raise ValueError("grid_levels must be at least 4.")
        if not 0 < self.range_pct < 0.25:
            raise ValueError("range_pct must be between 0 and 25%.")
        if not 0 < self.base_order_risk_pct <= 0.05:
            raise ValueError("base_order_risk_pct must be > 0 and <= 5%.")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")
        if self.leverage < 1 or self.leverage > 5:
            raise ValueError("For moderate risk, leverage must stay between 1x and 5x.")
