"""Core BTC grid engine used by the simulator and dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from .config import BotConfig
from .exchange import ExchangeAdapter, Order, PaperExchange


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
    exchange: ExchangeAdapter = field(default_factory=PaperExchange)


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
        previous_price = state.last_price
        state.tick_count += 1
        state.last_price = price
        state.prices.append(price)
        if len(state.prices) > 250:
            state.prices = state.prices[-250:]

        self._refresh_grid(price)
        state.mode = self._detect_mode()
        if self._is_spike_tick(previous_price, price):
            self._handle_spike_tick(price)
            return state

        self._open_positions_from_fills(state.exchange.process_price(price))
        self._update_risk_lock(price)
        self._close_positions(price)
        if state.trading_enabled:
            self._open_positions(price)
        return state

    def _is_spike_tick(self, previous_price: float | None, price: float) -> bool:
        if not previous_price:
            return False
        jump_pct = abs(price - previous_price) / previous_price
        return jump_pct >= self.config.max_tick_jump_pct

    def _handle_spike_tick(self, price: float) -> None:
        self.cancel_open_orders()
        self.state.mode = "PRICE_SPIKE_LOCK"
        self.state.cooldown_until_tick = max(
            self.state.cooldown_until_tick,
            self.state.tick_count + self.config.spike_cooldown_ticks,
        )
        self._update_risk_lock(price)
        self._close_positions(price)

    def snapshot(self) -> dict:
        price = self.state.last_price or 0.0
        unrealized = sum(position.unrealized_pnl(price) for position in self.state.positions)
        equity = self.state.balance + unrealized
        closed = len(self.state.trades)
        wins = sum(1 for trade in self.state.trades if trade.pnl > 0)
        return {
            "config": asdict(self.config),
            "exchange": self.state.exchange.status().to_dict(),
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
            "positions": [self._position_payload(position, price) for position in self.state.positions],
            "open_orders": [order.to_dict() for order in self.state.exchange.open_orders()],
            "recent_fills": [order.to_dict() for order in self.state.exchange.recent_fills()],
            "canceled_orders": [order.to_dict() for order in self.state.exchange.recent_canceled()],
            "trades": [asdict(trade) for trade in self.state.trades[-30:]][::-1],
            "tick_count": self.state.tick_count,
            "win_rate": (wins / closed * 100) if closed else 0.0,
            "closed_trades": closed,
            "grid_plan": self._grid_plan(price, equity),
        }

    def _position_payload(self, position: Position, price: float) -> dict:
        payload = asdict(position) | {"unrealized_pnl": position.unrealized_pnl(price)}
        payload["liquidation_price"] = self.state.exchange.liquidation_price(
            side=position.side,
            entry_price=position.entry_price,
            leverage=self.config.leverage,
        )
        return payload

    def _grid_plan(self, price: float, equity: float) -> dict:
        grid = self.state.grid
        open_orders = self.state.exchange.open_orders()
        open_notional = sum(position.notional for position in self.state.positions)
        pending_notional = sum(
            order.notional for order in open_orders if order.tag.startswith("grid_entry")
        )
        max_notional = equity * self.config.max_total_notional_pct if equity > 0 else 0.0
        next_margin = self.state.balance * self.config.base_order_risk_pct
        next_notional = next_margin * self.config.leverage
        entry_orders = [order for order in open_orders if order.tag.startswith("grid_entry")]
        position_slots_used = len(self.state.positions)
        pending_slots_used = len(entry_orders)
        long_pending = sum(1 for order in entry_orders if order.side == "BUY")
        short_pending = sum(1 for order in entry_orders if order.side == "SELL")
        spacing_pct = 0.0
        if len(grid) >= 2 and price:
            spacing_pct = (grid[1] - grid[0]) / price * 100
        return {
            "lower": grid[0] if grid else None,
            "upper": grid[-1] if grid else None,
            "step": (grid[1] - grid[0]) if len(grid) >= 2 else 0.0,
            "spacing_pct": spacing_pct,
            "slots_used": position_slots_used,
            "slots_remaining": max(0, self.config.max_open_positions - position_slots_used),
            "pending_slots_used": pending_slots_used,
            "pending_slots_remaining": max(0, self.config.max_pending_orders - pending_slots_used),
            "long_pending_orders": long_pending,
            "short_pending_orders": short_pending,
            "open_notional": open_notional,
            "pending_notional": pending_notional,
            "total_committed_notional": open_notional + pending_notional,
            "max_notional": max_notional,
            "next_order_notional": next_notional,
            "next_order_allowed_by_cap": (
                open_notional + pending_notional + next_notional <= max_notional
            ),
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
        if self.state.tick_count < self.state.cooldown_until_tick:
            return
        if self.state.mode == "WARMING_UP":
            return

        grid = self.state.grid
        step = grid[1] - grid[0]
        candidate_sides = self._candidate_entry_sides()

        self._cancel_stale_entry_orders(price=price, allowed_sides=candidate_sides, step=step)
        open_entry_orders = [
            order
            for order in self.state.exchange.open_orders()
            if order.tag.startswith("grid_entry")
        ]
        if len(self.state.positions) >= self.config.max_open_positions:
            return
        if len(open_entry_orders) >= self.config.max_pending_orders:
            return

        margin = self.state.balance * self.config.base_order_risk_pct
        notional = margin * self.config.leverage
        if notional <= 0:
            return
        if not self._within_notional_cap(price, notional, open_entry_orders):
            return

        entry_candidate = self._select_entry_candidate(
            candidate_sides=candidate_sides,
            price=price,
            step=step,
            open_entry_orders=open_entry_orders,
        )
        if not entry_candidate:
            return

        allowed_side, order_price, order_index = entry_candidate
        quantity = notional / order_price
        self.state.exchange.submit_limit_order(
            side="BUY" if allowed_side == "LONG" else "SELL",
            price=order_price,
            quantity=quantity,
            tag=f"grid_entry:{allowed_side}",
            grid_index=order_index,
        )
        self.state.cooldown_until_tick = self.state.tick_count + self.config.cooldown_ticks

    def _candidate_entry_sides(self) -> tuple[str, ...]:
        if self.state.mode == "RANGE":
            return ("LONG", "SHORT")
        if self.state.mode == "UPTREND":
            return ("LONG",)
        return ("SHORT",)

    def _select_entry_candidate(
        self,
        *,
        candidate_sides: tuple[str, ...],
        price: float,
        step: float,
        open_entry_orders: list[Order],
    ) -> tuple[str, float, int] | None:
        ranked: list[tuple[int, int, str, float, int]] = []
        for side in candidate_sides:
            expected_order_side = "BUY" if side == "LONG" else "SELL"
            side_pending = sum(1 for order in open_entry_orders if order.side == expected_order_side)
            if side_pending >= self.config.max_pending_orders_per_side:
                continue

            side_positions = sum(1 for position in self.state.positions if position.side == side)
            depth = side_pending + side_positions
            order_price = self._passive_order_price(price=price, side=side, step=step, depth=depth)
            order_index = self._nearest_grid_index(order_price)
            if self._has_nearby_entry(price=order_price, step=step, open_entry_orders=open_entry_orders):
                continue
            ranked.append((side_pending + side_positions, side_pending, side, order_price, order_index))

        if not ranked:
            return None
        _, _, side, order_price, order_index = min(ranked)
        return side, order_price, order_index

    def _passive_order_price(self, *, price: float, side: str, step: float, depth: int) -> float:
        offset = (depth + self.config.passive_entry_offset_steps) * step
        if side == "LONG":
            return max(step, price - offset)
        return price + offset

    def _nearest_grid_index(self, price: float) -> int:
        return min(range(len(self.state.grid)), key=lambda i: abs(self.state.grid[i] - price))

    def _has_nearby_entry(self, *, price: float, step: float, open_entry_orders: list[Order]) -> bool:
        nearby_position_exists = any(
            abs(position.entry_price - price) < step * 0.55 for position in self.state.positions
        )
        nearby_order_exists = any(abs(order.price - price) < step * 0.55 for order in open_entry_orders)
        return nearby_position_exists or nearby_order_exists

    def _cancel_stale_entry_orders(self, *, price: float, allowed_sides: tuple[str, ...], step: float) -> None:
        allowed_order_sides = {"BUY" if side == "LONG" else "SELL" for side in allowed_sides}
        for order in self.state.exchange.open_orders():
            if not order.tag.startswith("grid_entry"):
                continue
            too_far_from_grid = abs(order.price - price) > step * self.config.stale_order_grid_steps
            wrong_side_for_mode = order.side not in allowed_order_sides
            if too_far_from_grid or wrong_side_for_mode:
                self.state.exchange.cancel_order(order.order_id)

    def _within_notional_cap(
        self, price: float, next_notional: float, open_entry_orders: list[Order]
    ) -> bool:
        unrealized = sum(position.unrealized_pnl(price) for position in self.state.positions)
        equity = self.state.balance + unrealized
        max_notional = equity * self.config.max_total_notional_pct
        committed = sum(position.notional for position in self.state.positions)
        committed += sum(order.notional for order in open_entry_orders)
        return committed + next_notional <= max_notional

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

    def cancel_open_orders(self) -> int:
        """Cancel all currently open paper-exchange orders."""

        return self.state.exchange.cancel_all()

    def emergency_stop(self) -> int:
        """Disable new entries and cancel all open paper orders."""

        self.state.trading_enabled = False
        self.state.lock_reason = "Manual emergency stop; new entries disabled."
        return self.cancel_open_orders()

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
