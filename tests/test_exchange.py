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


def test_paper_exchange_applies_symbol_filters_and_status():
    exchange = PaperExchange()
    order = exchange.submit_limit_order(side="BUY", price=100.009, quantity=0.1234567)

    assert order.price == 100.0
    assert order.quantity == 0.123456
    assert order.notional >= exchange.filters.min_notional

    exchange.process_price(99.0)
    status = exchange.status().to_dict()

    assert status["mode"] == "LOCAL_EMULATOR"
    assert status["can_place_orders"] is True
    assert status["mark_price"] == 99.0
    assert status["filters"]["symbol"] == "BTCUSDT"


def test_paper_exchange_rejects_orders_below_min_notional():
    exchange = PaperExchange()

    try:
        exchange.submit_limit_order(side="BUY", price=100.0, quantity=0.001)
    except ValueError as exc:
        assert "below minimum" in str(exc)
    else:
        raise AssertionError("orders below min_notional should be rejected")


def test_testnet_adapter_is_read_only_skeleton():
    from botify.exchange import BinanceFuturesTestnetAdapter

    adapter = BinanceFuturesTestnetAdapter(api_key="key", api_secret="secret")
    status = adapter.status().to_dict()

    assert status["mode"] == "TESTNET_READ_ONLY"
    assert status["testnet"] is True
    assert status["can_place_orders"] is False
    assert adapter.open_orders() == []

    try:
        adapter.submit_limit_order(side="BUY", price=100.0, quantity=0.1)
    except NotImplementedError as exc:
        assert "disabled" in str(exc)
    else:
        raise AssertionError("testnet order placement should remain disabled")
