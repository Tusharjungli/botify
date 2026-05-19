from botify.exchange import PaperExchange


def test_paper_exchange_limit_order_lifecycle():
    exchange = PaperExchange()
    order = exchange.submit_limit_order(side="BUY", price=100.0, quantity=0.5, tag="unit")

    assert order.status == "NEW"
    assert exchange.process_price(101.0) == []
    assert exchange.open_orders() == [order]

    fills = exchange.process_price(99.0)

    assert fills == [order]
    assert order.status == "FILLED"
    assert order.average_fill_price == 100.0
    assert exchange.open_orders() == []
    assert exchange.recent_fills() == [order]


def test_paper_exchange_can_cancel_open_orders():
    exchange = PaperExchange()
    first = exchange.submit_limit_order(side="SELL", price=110.0, quantity=0.2, tag="grid_entry")
    second = exchange.submit_limit_order(side="BUY", price=90.0, quantity=0.2, tag="other")

    assert exchange.cancel_order(first.order_id) is True
    assert first.status == "CANCELED"
    assert second in exchange.open_orders()

    assert exchange.cancel_all() == 1
    assert second.status == "CANCELED"
    assert exchange.open_orders() == []


def test_paper_exchange_records_created_tick():
    exchange = PaperExchange()
    order = exchange.submit_limit_order(side="BUY", price=100.0, quantity=0.5, created_tick=42)

    assert order.created_tick == 42
    assert order.to_dict()["created_tick"] == 42
