from botify.config import BotConfig
from botify.engine import GridEngine
from botify.market import DeterministicPriceFeed


def test_config_is_btc_only():
    try:
        BotConfig(symbol="ETHUSDT").validate()
    except ValueError as exc:
        assert "BTC-only" in str(exc)
    else:
        raise AssertionError("non-BTC symbol should be rejected")


def test_engine_builds_grid_and_snapshot():
    engine = GridEngine(BotConfig())
    feed = DeterministicPriceFeed(start_price=100_000)

    for _ in range(30):
        engine.on_price(feed.latest_price())

    snapshot = engine.snapshot()
    assert snapshot["config"]["symbol"] == "BTCUSDT"
    assert snapshot["tick_count"] == 30
    assert len(snapshot["grid"]) == snapshot["config"]["grid_levels"] + 1
    assert snapshot["mode"] in {"RANGE", "UPTREND", "DOWNTREND", "WARMING_UP"}


def test_daily_loss_lock_disables_new_entries():
    config = BotConfig(starting_balance=10_000, max_daily_loss_pct=0.001)
    engine = GridEngine(config)
    engine.state.balance = 9_980

    engine.on_price(100_000)
    snapshot = engine.snapshot()

    assert snapshot["trading_enabled"] is False
    assert "Daily max loss" in snapshot["lock_reason"]


def test_engine_routes_entries_through_paper_exchange_orders():
    engine = GridEngine(BotConfig(cooldown_ticks=1, trading_bias="LONG"))
    for _ in range(21):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    assert snapshot["mode"] == "RANGE"
    assert snapshot["positions"] == []
    assert len(snapshot["open_orders"]) == 1
    assert snapshot["open_orders"][0]["status"] == "NEW"
    assert snapshot["open_orders"][0]["side"] == "BUY"
    assert snapshot["open_orders"][0]["price"] < snapshot["price"]

    engine.on_price(snapshot["open_orders"][0]["price"] * 0.999)
    snapshot = engine.snapshot()

    assert len(snapshot["recent_fills"]) == 1
    assert len(snapshot["positions"]) == 1
    assert snapshot["positions"][0]["side"] == "LONG"


def test_emergency_stop_cancels_orders_and_locks_entries():
    engine = GridEngine(BotConfig(cooldown_ticks=1))
    engine.state.exchange.submit_limit_order(side="BUY", price=99_000, quantity=0.01)

    canceled = engine.emergency_stop()
    engine.on_price(100_000)
    snapshot = engine.snapshot()

    assert canceled == 1
    assert snapshot["trading_enabled"] is False
    assert "Manual emergency stop" in snapshot["lock_reason"]
    assert snapshot["open_orders"] == []
    assert snapshot["canceled_orders"][0]["status"] == "CANCELED"


def test_neutral_bias_places_two_sided_range_orders():
    engine = GridEngine(BotConfig(cooldown_ticks=1, trading_bias="NEUTRAL"))
    for _ in range(21):
        engine.on_price(100_000)

    snapshot = engine.snapshot()

    assert {order["side"] for order in snapshot["open_orders"]} == {"BUY", "SELL"}
    assert min(order["price"] for order in snapshot["open_orders"]) < snapshot["price"]
    assert max(order["price"] for order in snapshot["open_orders"]) > snapshot["price"]


def test_stale_orders_are_canceled_before_new_entries():
    engine = GridEngine(BotConfig(cooldown_ticks=1, max_order_age_ticks=2))
    for _ in range(21):
        engine.on_price(100_000)

    first_order_id = engine.snapshot()["open_orders"][0]["order_id"]
    engine.on_price(100_100)
    engine.on_price(100_200)

    snapshot = engine.snapshot()

    assert any(order["order_id"] == first_order_id for order in snapshot["canceled_orders"])


def test_config_accepts_optimizer_and_paper_session_fields():
    from dataclasses import replace

    config = replace(
        BotConfig(),
        passive_entry_offset_steps=0.5,
        trend_flip_min_loss_pct=0.006,
    )

    assert config.passive_entry_offset_steps == 0.5
    assert config.trend_flip_min_loss_pct == 0.006


def test_fractional_passive_entry_offset_is_used_for_orders():
    engine = GridEngine(BotConfig(cooldown_ticks=1, passive_entry_offset_steps=0.5, trading_bias="LONG"))
    for _ in range(21):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    step = snapshot["grid"][1] - snapshot["grid"][0]
    order = snapshot["open_orders"][0]

    assert order["side"] == "BUY"
    assert abs(order["price"] - (snapshot["price"] - step * 0.5)) < 0.01
