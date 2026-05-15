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
    engine = GridEngine(BotConfig(cooldown_ticks=1))
    for _ in range(21):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    assert snapshot["mode"] == "RANGE"
    assert snapshot["positions"] == []
    assert len(snapshot["open_orders"]) == 1
    assert snapshot["open_orders"][0]["status"] == "NEW"

    order = snapshot["open_orders"][0]
    fill_price = order["price"]
    engine.on_price(fill_price - 1 if order["side"] == "BUY" else fill_price + 1)
    snapshot = engine.snapshot()

    assert len(snapshot["recent_fills"]) == 1
    assert len(snapshot["positions"]) == 1
    assert snapshot["positions"][0]["side"] in {"LONG", "SHORT"}


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


def test_pending_orders_have_separate_capacity_from_positions():
    config = BotConfig(cooldown_ticks=1, max_open_positions=1, max_pending_orders=2, max_pending_orders_per_side=1)
    engine = GridEngine(config)
    engine.state.exchange.submit_limit_order(
        side="BUY", price=99_000, quantity=0.01, tag="grid_entry:LONG"
    )

    snapshot = engine.snapshot()

    assert len(snapshot["open_orders"]) == 1
    assert snapshot["grid_plan"]["slots_used"] == 0
    assert snapshot["grid_plan"]["slots_remaining"] == 1
    assert snapshot["grid_plan"]["pending_slots_used"] == 1
    assert snapshot["grid_plan"]["pending_slots_remaining"] == 1


def test_notional_cap_blocks_new_grid_orders():
    config = BotConfig(cooldown_ticks=1, max_total_notional_pct=0.01)
    engine = GridEngine(config)

    for _ in range(25):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    assert snapshot["open_orders"] == []
    assert snapshot["grid_plan"]["next_order_allowed_by_cap"] is False


def test_stale_or_wrong_side_orders_are_canceled_before_new_entries():
    config = BotConfig(cooldown_ticks=1, stale_order_grid_steps=1)
    engine = GridEngine(config)
    engine.state.exchange.submit_limit_order(
        side="BUY", price=90_000, quantity=0.01, tag="grid_entry:LONG"
    )

    for _ in range(25):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    assert any(order["status"] == "CANCELED" for order in snapshot["canceled_orders"])
    assert all(order["price"] != 90_000 for order in snapshot["open_orders"])


def test_spike_tick_cancels_pending_orders_before_they_fill():
    config = BotConfig(cooldown_ticks=1, max_tick_jump_pct=0.03, spike_cooldown_ticks=5)
    engine = GridEngine(config)
    engine.on_price(100_000)
    engine.state.exchange.submit_limit_order(
        side="BUY", price=100_000, quantity=0.01, tag="grid_entry:LONG"
    )

    engine.on_price(80_000)
    snapshot = engine.snapshot()

    assert snapshot["mode"] == "PRICE_SPIKE_LOCK"
    assert snapshot["recent_fills"] == []
    assert snapshot["open_orders"] == []
    assert snapshot["canceled_orders"][0]["status"] == "CANCELED"
    assert engine.state.cooldown_until_tick > engine.state.tick_count


def test_entries_use_passive_grid_levels_not_nearest_marketable_price():
    engine = GridEngine(BotConfig(cooldown_ticks=1))

    for _ in range(21):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    order = snapshot["open_orders"][0]

    assert order["side"] == "BUY"
    assert order["price"] < snapshot["price"]
    assert snapshot["price"] - order["price"] < snapshot["grid_plan"]["step"]


def test_pending_order_capacity_blocks_new_grid_orders():
    config = BotConfig(cooldown_ticks=1, max_pending_orders=1, max_pending_orders_per_side=1)
    engine = GridEngine(config)
    engine.state.exchange.submit_limit_order(
        side="SELL", price=101_000, quantity=0.01, tag="grid_entry:SHORT"
    )

    for _ in range(25):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    assert len(snapshot["open_orders"]) == 1
    assert snapshot["grid_plan"]["pending_slots_remaining"] == 0


def test_range_mode_builds_balanced_ladder_without_duplicate_prices():
    config = BotConfig(cooldown_ticks=1, max_pending_orders=12, max_pending_orders_per_side=6)
    engine = GridEngine(config)

    for _ in range(80):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    open_orders = snapshot["open_orders"]
    buy_orders = [order for order in open_orders if order["side"] == "BUY"]
    sell_orders = [order for order in open_orders if order["side"] == "SELL"]
    prices = [order["price"] for order in open_orders]

    assert snapshot["mode"] == "RANGE"
    assert len(buy_orders) == config.max_pending_orders_per_side
    assert len(sell_orders) == config.max_pending_orders_per_side
    assert all(order["price"] < snapshot["price"] for order in buy_orders)
    assert all(order["price"] > snapshot["price"] for order in sell_orders)
    assert len(prices) == len(set(prices))


def test_range_mode_keeps_both_sides_when_canceling_stale_orders():
    config = BotConfig(cooldown_ticks=1, stale_order_grid_steps=3)
    engine = GridEngine(config)
    engine.state.exchange.submit_limit_order(
        side="BUY", price=99_000, quantity=0.01, tag="grid_entry:LONG"
    )
    engine.state.exchange.submit_limit_order(
        side="SELL", price=101_000, quantity=0.01, tag="grid_entry:SHORT"
    )

    for _ in range(25):
        engine.on_price(100_000)

    snapshot = engine.snapshot()
    open_sides = {order["side"] for order in snapshot["open_orders"]}

    assert snapshot["mode"] == "RANGE"
    assert {"BUY", "SELL"}.issubset(open_sides)


def test_tighter_passive_offset_allows_small_range_move_to_fill():
    engine = GridEngine(BotConfig(cooldown_ticks=1))

    for _ in range(21):
        engine.on_price(100_000)

    first_order = engine.snapshot()["open_orders"][0]
    assert first_order["side"] == "BUY"
    assert 100_000 - first_order["price"] < engine.snapshot()["grid_plan"]["step"]

    engine.on_price(99_880)
    snapshot = engine.snapshot()

    assert len(snapshot["recent_fills"]) == 1
    assert len(snapshot["positions"]) == 1
    assert snapshot["positions"][0]["side"] == "LONG"
