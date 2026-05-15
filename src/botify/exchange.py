"""Local and testnet exchange adapters for Botify simulations.

The project still defaults to a local emulator.  The Binance Futures testnet
adapter is intentionally a skeleton so signed order placement can be added only
after the simulator and readiness gates are stable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import floor
from typing import Protocol


@dataclass(frozen=True)
class SymbolFilters:
    """Binance-style symbol constraints used before accepting orders."""

    symbol: str = "BTCUSDT"
    tick_size: float = 0.01
    step_size: float = 0.000001
    min_notional: float = 5.0
    max_leverage: float = 5.0
    maintenance_margin_pct: float = 0.004

    def normalize_price(self, price: float) -> float:
        return _round_down(price, self.tick_size)

    def normalize_quantity(self, quantity: float) -> float:
        return _round_down(quantity, self.step_size)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExchangeStatus:
    """Public status for dashboard/readiness checks."""

    name: str
    mode: str
    symbol: str
    testnet: bool
    can_place_orders: bool
    mark_price: float | None
    funding_rate_pct: float
    filters: dict
    last_error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Order:
    """A simulated exchange order with a small Binance-like lifecycle."""

    order_id: int
    client_order_id: str
    side: str
    price: float
    quantity: float
    reduce_only: bool = False
    tag: str = "grid_entry"
    grid_index: int | None = None
    status: str = "NEW"
    order_type: str = "LIMIT"
    created_at: str = field(default_factory=lambda: _now())
    filled_at: str | None = None
    average_fill_price: float | None = None
    canceled_at: str | None = None
    reject_reason: str = ""

    @property
    def notional(self) -> float:
        return self.price * self.quantity

    def to_dict(self) -> dict:
        return asdict(self) | {"notional": self.notional}


class ExchangeAdapter(Protocol):
    """Minimal exchange boundary used by the grid engine."""

    def submit_limit_order(
        self,
        *,
        side: str,
        price: float,
        quantity: float,
        reduce_only: bool = False,
        tag: str = "grid_entry",
        grid_index: int | None = None,
    ) -> Order:
        """Submit a limit order and return the local/exchange order model."""

    def process_price(self, price: float) -> list[Order]:
        """Advance local fills from a market price tick."""

    def cancel_order(self, order_id: int) -> bool:
        """Cancel one open order."""

    def cancel_all(self, tag: str | None = None) -> int:
        """Cancel open orders, optionally restricted by tag."""

    def open_orders(self) -> list[Order]:
        """Return currently open orders."""

    def recent_fills(self, limit: int = 30) -> list[Order]:
        """Return recent filled orders."""

    def recent_canceled(self, limit: int = 30) -> list[Order]:
        """Return recent canceled orders."""

    def liquidation_price(self, *, side: str, entry_price: float, leverage: float) -> float:
        """Estimate liquidation price for a local/testnet position."""

    def status(self) -> ExchangeStatus:
        """Return public exchange mode/status metadata."""


class PaperExchange:
    """Local Binance Futures-style emulator for limit-order simulations.

    The emulator validates price/quantity filters, tracks mark price and a
    placeholder funding rate, and fills marketable limit orders as prices cross.
    It remains deterministic and local: no API keys and no live orders.
    """

    def __init__(
        self,
        *,
        filters: SymbolFilters | None = None,
        name: str = "Local Futures Emulator",
        mode: str = "LOCAL_EMULATOR",
    ) -> None:
        self._next_order_id = 1
        self.filters = filters or SymbolFilters()
        self.name = name
        self.mode = mode
        self.orders: list[Order] = []
        self.mark_price: float | None = None
        self.funding_rate_pct: float = 0.0
        self.last_error = ""

    def submit_limit_order(
        self,
        *,
        side: str,
        price: float,
        quantity: float,
        reduce_only: bool = False,
        tag: str = "grid_entry",
        grid_index: int | None = None,
    ) -> Order:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if price <= 0:
            raise ValueError("price must be positive")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        normalized_price = self.filters.normalize_price(price)
        normalized_quantity = self.filters.normalize_quantity(quantity)
        if normalized_price <= 0 or normalized_quantity <= 0:
            raise ValueError("price and quantity are below symbol precision filters")
        notional = normalized_price * normalized_quantity
        if notional < self.filters.min_notional:
            raise ValueError(
                f"order notional ${notional:,.2f} is below minimum ${self.filters.min_notional:,.2f}"
            )

        order = Order(
            order_id=self._next_order_id,
            client_order_id=f"botify-{self._next_order_id:08d}",
            side=side,
            price=normalized_price,
            quantity=normalized_quantity,
            reduce_only=reduce_only,
            tag=tag,
            grid_index=grid_index,
        )
        self._next_order_id += 1
        self.orders.append(order)
        return order

    def process_price(self, price: float) -> list[Order]:
        """Fill marketable NEW limit orders for the given last price."""

        self.mark_price = price
        filled: list[Order] = []
        for order in self.open_orders():
            if _is_marketable(order, price):
                order.status = "FILLED"
                order.filled_at = _now()
                order.average_fill_price = order.price
                filled.append(order)
        return filled

    def cancel_order(self, order_id: int) -> bool:
        for order in self.orders:
            if order.order_id == order_id and order.status == "NEW":
                order.status = "CANCELED"
                order.canceled_at = _now()
                return True
        return False

    def cancel_all(self, tag: str | None = None) -> int:
        canceled = 0
        for order in self.open_orders():
            if tag is None or order.tag == tag:
                order.status = "CANCELED"
                order.canceled_at = _now()
                canceled += 1
        return canceled

    def open_orders(self) -> list[Order]:
        return [order for order in self.orders if order.status == "NEW"]

    def recent_fills(self, limit: int = 30) -> list[Order]:
        return [order for order in self.orders if order.status == "FILLED"][-limit:][::-1]

    def recent_canceled(self, limit: int = 30) -> list[Order]:
        return [order for order in self.orders if order.status == "CANCELED"][-limit:][::-1]

    def liquidation_price(self, *, side: str, entry_price: float, leverage: float) -> float:
        """Estimate an isolated-margin liquidation level for dashboard warnings."""

        margin_pct = 1 / leverage
        maintenance = self.filters.maintenance_margin_pct
        if side == "LONG":
            return entry_price * (1 - margin_pct + maintenance)
        if side == "SHORT":
            return entry_price * (1 + margin_pct - maintenance)
        raise ValueError("side must be LONG or SHORT")

    def status(self) -> ExchangeStatus:
        return ExchangeStatus(
            name=self.name,
            mode=self.mode,
            symbol=self.filters.symbol,
            testnet=False,
            can_place_orders=True,
            mark_price=self.mark_price,
            funding_rate_pct=self.funding_rate_pct,
            filters=self.filters.to_dict(),
            last_error=self.last_error,
        )


class BinanceFuturesTestnetAdapter:
    """Read-only Binance Futures testnet adapter skeleton.

    This class deliberately does not implement signed network calls yet.  It is
    a safe seam for the next milestone: exchange-info filters, account reads,
    user-stream reconciliation, then testnet-only order placement.
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        filters: SymbolFilters | None = None,
        enable_order_placement: bool = False,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.filters = filters or SymbolFilters()
        self.enable_order_placement = enable_order_placement
        self.last_error = "Signed Binance Futures testnet calls are not implemented yet."

    def submit_limit_order(
        self,
        *,
        side: str,
        price: float,
        quantity: float,
        reduce_only: bool = False,
        tag: str = "grid_entry",
        grid_index: int | None = None,
    ) -> Order:
        raise NotImplementedError(
            "Testnet order placement is intentionally disabled until signed REST support is added."
        )

    def process_price(self, price: float) -> list[Order]:
        return []

    def cancel_order(self, order_id: int) -> bool:
        return False

    def cancel_all(self, tag: str | None = None) -> int:
        return 0

    def open_orders(self) -> list[Order]:
        return []

    def recent_fills(self, limit: int = 30) -> list[Order]:
        return []

    def recent_canceled(self, limit: int = 30) -> list[Order]:
        return []

    def liquidation_price(self, *, side: str, entry_price: float, leverage: float) -> float:
        return PaperExchange(filters=self.filters).liquidation_price(
            side=side, entry_price=entry_price, leverage=leverage
        )

    def status(self) -> ExchangeStatus:
        return ExchangeStatus(
            name="Binance Futures Testnet",
            mode="TESTNET_READ_ONLY",
            symbol=self.filters.symbol,
            testnet=True,
            can_place_orders=False,
            mark_price=None,
            funding_rate_pct=0.0,
            filters=self.filters.to_dict(),
            last_error=self.last_error,
        )


def _is_marketable(order: Order, price: float) -> bool:
    if order.side == "BUY":
        return price <= order.price
    return price >= order.price


def _round_down(value: float, step: float) -> float:
    if step <= 0:
        raise ValueError("step must be positive")
    precision = max(0, len(f"{step:.12f}".rstrip("0").split(".")[-1]))
    return round(floor(value / step) * step, precision)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
