"""Core BTC grid engine used by the simulator and dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from statistics import mean

from .config import BotConfig
from .exchange import Order, PaperExchange


@dataclass
class Position:
    """A simulated grid position."""

    side: str
    entry_price: float
    notional: float
    quantity: float
    opened_at: str
    target_price: float
    stop_price: float
    peak_price: float
    trough_price: float
    grid_index: int

    def unrealized_pnl(self, price: float) -> float:
        if self.side == "LONG":
            return (price - self.entry_price) * self.quantity
        return (self.entry_price - price) * self.quantity


@dataclass
class Trade:
    """A closed simulated trade."""

    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    reason: str
    opened_at: str
    closed_at: str


@dataclass
class BotState:
    """Current account, grid, and performance state."""

    balance: float
    daily_start_balance: float
    trading_enabled: bool = True
    lock_reason: str = ""
    prices: list[float] = field(default_factory=list)
    grid: list[float] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    tick_count: int = 0
    cooldown_until_tick: int = 0
    mode: str = "WARMING_UP"
    last_price: float | None = None
    realized_pnl: float = 0.0
    exchange: PaperExchange = field(default_factory=PaperExchange)


class GridEngine:
    """Moderate-risk BTC-only grid strategy simulator.

    This engine deliberately models orders and fees locally. It does not submit
    real orders to Binance. The live trading adapter should only be added after
    the simulator, backtests, and paper-trading checks are stable.
    """

    def __init__(self, config: BotConfig | None = None) -> None:
        self.config = config or BotConfig()
        self.config.validate()
        self.state = BotState(
            balance=self.config.starting_balance,
            daily_start_balance=self.config.starting_balance,
        )

    def on_price(self, price: float) -> BotState:
        if price <= 0:
            raise ValueError("price must be positive")

        state = self.state
        state.tick_count += 1
        state.last_price = price
        state.prices.append(price)
        if len(state.prices) > 250:
            state.prices = state.prices[-250:]

        self._refresh_grid(price)
        state.mode = self._detect_mode()
        self._open_positions_from_fills(state.exchange.process_price(price))
        self._update_risk_lock(price)
        self._close_positions(price)
        if state.trading_enabled:
            self._open_positions(price)
        return state

    def snapshot(self) -> dict:
        price = self.state.last_price or 0.0
        unrealized = sum(position.unrealized_pnl(price) for position in self.state.positions)
        equity = self.state.balance + unrealized
        closed = len(self.state.trades)
        wins = sum(1 for trade in self.state.trades if trade.pnl > 0)
        return {
            "config": asdict(self.config),
            "price": price,
            "mode": self.state.mode,
            "balance": self.state.balance,
            "equity": equity,
            "realized_pnl": self.state.realized_pnl,
            "unrealized_pnl": unrealized,
            "daily_pnl_pct": self._daily_pnl_pct(equity),
            "trading_enabled": self.state.trading_enabled,
            "lock_reason": self.state.lock_reason,
            "grid": self.state.grid,
            "positions": [asdict(position) | {"unrealized_pnl": position.unrealized_pnl(price)} for position in self.state.positions],
            "open_orders": [order.to_dict() for order in self.state.exchange.open_orders()],
            "recent_fills": [order.to_dict() for order in self.state.exchange.recent_fills()],
            "canceled_orders": [order.to_dict() for order in self.state.exchange.recent_canceled()],
            "trades": [asdict(trade) for trade in self.state.trades[-30:]][::-1],
            "tick_count": self.state.tick_count,
            "win_rate": (wins / closed * 100) if closed else 0.0,
            "closed_trades": closed,
        }

    def _refresh_grid(self, price: float) -> None:
        if len(self.state.prices) >= 20:
            recent = self.state.prices[-50:]
            high = max(recent)
            low = min(recent)
            dynamic_range = max(self.config.range_pct, (high - low) / max(low, 1) * 1.4)
            dynamic_range = min(dynamic_range, 0.10)
        else:
            dynamic_range = self.config.range_pct

        lower = price * (1 - dynamic_range)
        upper = price * (1 + dynamic_range)
        step = (upper - lower) / self.config.grid_levels
        self.state.grid = [lower + i * step for i in range(self.config.grid_levels + 1)]

    def _detect_mode(self) -> str:
        prices = self.state.prices
        if len(prices) < self.config.ema_slow:
            return "WARMING_UP"
        fast = _ema(prices, self.config.ema_fast)
        slow = _ema(prices, self.config.ema_slow)
        strength = abs(fast - slow) / prices[-1]
        if strength < self.config.trend_strength_threshold:
            return "RANGE"
        return "UPTREND" if fast > slow else "DOWNTREND"

    def _update_risk_lock(self, price: float) -> None:
        equity = self.state.balance + sum(position.unrealized_pnl(price) for position in self.state.positions)
        daily_pnl_pct = self._daily_pnl_pct(equity)
        if daily_pnl_pct <= -self.config.max_daily_loss_pct:
            self.state.trading_enabled = False
            self.state.lock_reason = "Daily max loss reached; new entries disabled."
        elif daily_pnl_pct >= self.config.daily_profit_lock_pct:
            self.state.trading_enabled = False
            self.state.lock_reason = "Daily profit lock reached; new entries disabled."
        elif not self.state.lock_reason:
            self.state.trading_enabled = True

    def _open_positions(self, price: float) -> None:
        if len(self.state.positions) >= self.config.max_open_positions:
            return
        if self.state.tick_count < self.state.cooldown_until_tick:
            return
        if self.state.mode == "WARMING_UP":
            return

        grid = self.state.grid
        step = grid[1] - grid[0]
        middle = mean((grid[0], grid[-1]))
        index = min(range(len(grid)), key=lambda i: abs(grid[i] - price))

        allowed_side: str | None
        if self.state.mode == "RANGE":
            allowed_side = "LONG" if price < middle else "SHORT"
        elif self.state.mode == "UPTREND":
            allowed_side = "LONG"
        else:
            allowed_side = "SHORT"

        nearby_position_exists = any(abs(position.entry_price - price) < step * 0.55 for position in self.state.positions)
        nearby_order_exists = any(abs(order.price - price) < step * 0.55 for order in self.state.exchange.open_orders())
        if nearby_position_exists or nearby_order_exists:
            return

        margin = self.state.balance * self.config.base_order_risk_pct
        notional = margin * self.config.leverage
        if notional <= 0:
            return

        order_price = grid[index]
        quantity = notional / order_price
        self.state.exchange.submit_limit_order(
            side="BUY" if allowed_side == "LONG" else "SELL",
            price=order_price,
            quantity=quantity,
            tag=f"grid_entry:{allowed_side}",
            grid_index=index,
        )
        self.state.cooldown_until_tick = self.state.tick_count + self.config.cooldown_ticks

    def _open_positions_from_fills(self, filled_orders: list[Order]) -> None:
        if not filled_orders or len(self.state.grid) < 2:
            return

        step = self.state.grid[1] - self.state.grid[0]
        for order in filled_orders:
            if order.reduce_only or not order.tag.startswith("grid_entry"):
                continue
            if len(self.state.positions) >= self.config.max_open_positions:
                continue

            side = "LONG" if order.side == "BUY" else "SHORT"
            entry_price = order.average_fill_price or order.price
            notional = order.notional
            fee = notional * self.config.maker_fee_pct
            if self.state.balance <= fee:
                continue

            if side == "LONG":
                target = entry_price + step * self.config.take_profit_grid_steps
                stop = entry_price * (1 - self.config.stop_loss_pct)
            else:
                target = entry_price - step * self.config.take_profit_grid_steps
                stop = entry_price * (1 + self.config.stop_loss_pct)

            self.state.balance -= fee
            self.state.positions.append(
                Position(
                    side=side,
                    entry_price=entry_price,
                    notional=notional,
                    quantity=order.quantity,
                    opened_at=order.filled_at or _now(),
                    target_price=target,
                    stop_price=stop,
                    peak_price=entry_price,
                    trough_price=entry_price,
                    grid_index=order.grid_index or 0,
                )
            )

    def _close_positions(self, price: float) -> None:
        still_open: list[Position] = []
        for position in self.state.positions:
            position.peak_price = max(position.peak_price, price)
            position.trough_price = min(position.trough_price, price)
            reason = self._exit_reason(position, price)
            if reason:
                gross_pnl = position.unrealized_pnl(price)
                exit_fee = position.notional * self.config.taker_fee_pct
                pnl = gross_pnl - exit_fee
                self.state.balance += pnl
                self.state.realized_pnl += pnl
                self.state.trades.append(
                    Trade(
                        side=position.side,
                        entry_price=position.entry_price,
                        exit_price=price,
                        quantity=position.quantity,
                        pnl=pnl,
                        reason=reason,
                        opened_at=position.opened_at,
                        closed_at=_now(),
                    )
                )
            else:
                still_open.append(position)
        self.state.positions = still_open

    def _exit_reason(self, position: Position, price: float) -> str | None:
        profit_pct = abs(price - position.entry_price) / position.entry_price
        if position.side == "LONG":
            if price >= position.target_price and profit_pct >= self.config.min_grid_profit_pct:
                return "grid_take_profit"
            if price <= position.stop_price:
                return "stop_loss"
            if price <= position.peak_price * (1 - self.config.trailing_stop_pct) and price > position.entry_price:
                return "trailing_profit"
            if self.state.mode == "DOWNTREND" and price < position.entry_price:
                return "trend_flip"
        else:
            if price <= position.target_price and profit_pct >= self.config.min_grid_profit_pct:
                return "grid_take_profit"
            if price >= position.stop_price:
                return "stop_loss"
            if price >= position.trough_price * (1 + self.config.trailing_stop_pct) and price < position.entry_price:
                return "trailing_profit"
            if self.state.mode == "UPTREND" and price > position.entry_price:
                return "trend_flip"
        return None

    def _daily_pnl_pct(self, equity: float) -> float:
        return (equity - self.state.daily_start_balance) / self.state.daily_start_balance


def _ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
