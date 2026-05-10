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
