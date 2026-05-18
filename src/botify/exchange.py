"""Local paper-exchange order lifecycle for Botify simulations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


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
    created_tick: int = 0
    status: str = "NEW"
    order_type: str = "LIMIT"
    created_at: str = field(default_factory=lambda: _now())
    filled_at: str | None = None
    average_fill_price: float | None = None
    canceled_at: str | None = None

    @property
    def notional(self) -> float:
        return self.price * self.quantity

    def to_dict(self) -> dict:
        return asdict(self) | {"notional": self.notional}


class PaperExchange:
    """Very small local exchange emulator for limit orders.

    The engine submits limit orders here first, then asks the exchange to fill
    them as prices cross. This keeps Botify simulation-only while making the
    order flow closer to a futures grid bot before any Binance testnet work.
    """

    def __init__(self) -> None:
        self._next_order_id = 1
        self.orders: list[Order] = []

    def submit_limit_order(
        self,
        *,
        side: str,
        price: float,
        quantity: float,
        reduce_only: bool = False,
        tag: str = "grid_entry",
        grid_index: int | None = None,
        created_tick: int = 0,
    ) -> Order:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if price <= 0:
            raise ValueError("price must be positive")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        order = Order(
            order_id=self._next_order_id,
            client_order_id=f"botify-{self._next_order_id:08d}",
            side=side,
            price=price,
            quantity=quantity,
            reduce_only=reduce_only,
            tag=tag,
            grid_index=grid_index,
            created_tick=created_tick,
        )
        self._next_order_id += 1
        self.orders.append(order)
        return order

    def process_price(self, price: float) -> list[Order]:
        """Fill marketable NEW limit orders for the given last price."""

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


def _is_marketable(order: Order, price: float) -> bool:
    if order.side == "BUY":
        return price <= order.price
    return price >= order.price


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
