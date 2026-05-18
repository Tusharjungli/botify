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
    grid_levels: int = 12
    range_pct: float = 0.05
    leverage: float = 2.0
    base_order_risk_pct: float = 0.0125
    max_open_positions: int = 6
    max_open_orders: int = 4
    entry_grid_offset: int = 1
    passive_entry_offset_steps: float = 1.0
    trading_bias: str = "NEUTRAL"
    max_order_age_ticks: int = 12
    max_daily_loss_pct: float = 0.025
    daily_profit_lock_pct: float = 0.035
    stop_loss_pct: float = 0.05
    take_profit_grid_steps: int = 3
    maker_fee_pct: float = 0.0002
    taker_fee_pct: float = 0.0005
    trailing_stop_pct: float = 0.004
    min_grid_profit_pct: float = 0.0015
    trend_flip_min_loss_pct: float = 0.0
    cooldown_ticks: int = 2
    ema_fast: int = 9
    ema_slow: int = 21
    trend_strength_threshold: float = 0.00035

    def validate(self) -> None:
        if self.symbol != "BTCUSDT":
            raise ValueError("Botify milestone 1 is BTC-only. Use symbol='BTCUSDT'.")
        if self.trading_bias not in {"LONG", "SHORT", "NEUTRAL"}:
            raise ValueError("trading_bias must be LONG, SHORT, or NEUTRAL.")
        if self.grid_levels < 4:
            raise ValueError("grid_levels must be at least 4.")
        if not 0 < self.range_pct < 0.25:
            raise ValueError("range_pct must be between 0 and 25%.")
        if not 0 < self.base_order_risk_pct <= 0.05:
            raise ValueError("base_order_risk_pct must be > 0 and <= 5%.")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")
        if self.max_open_orders < 1:
            raise ValueError("max_open_orders must be at least 1.")
        if self.entry_grid_offset < 1:
            raise ValueError("entry_grid_offset must be at least 1.")
        if self.passive_entry_offset_steps <= 0:
            raise ValueError("passive_entry_offset_steps must be positive.")
        if self.take_profit_grid_steps < 1:
            raise ValueError("take_profit_grid_steps must be at least 1.")
        if self.max_order_age_ticks < 1:
            raise ValueError("max_order_age_ticks must be at least 1.")
        if not 0 < self.stop_loss_pct < 0.25:
            raise ValueError("stop_loss_pct must be between 0 and 25%.")
        if self.trend_flip_min_loss_pct < 0:
            raise ValueError("trend_flip_min_loss_pct must be non-negative.")
        if self.leverage < 1 or self.leverage > 5:
            raise ValueError("For moderate risk, leverage must stay between 1x and 5x.")
