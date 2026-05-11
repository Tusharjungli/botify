from botify import app


def test_pause_toggle_and_reset_controls():
    app.reset_simulation()
    assert app.control_state()["paused"] is False

    paused_snapshot = app.toggle_pause()
    assert paused_snapshot["paused"] is True
    assert app.control_state()["paused"] is True

    reset_snapshot = app.reset_simulation()
    assert reset_snapshot["paused"] is False
    assert reset_snapshot["tick_count"] == 0
    assert reset_snapshot["positions"] == []
    assert reset_snapshot["trades"] == []


def test_quick_backtest_result_is_stored_on_dashboard_state():
    app.reset_simulation()
    result = app.run_quick_backtest(limit=60)

    assert result["report"]["source"] == "synthetic_dashboard"
    assert result["report"]["candles"] == 60
    assert result["report"]["ending_equity"] > 0

    snapshot = app.snapshot_with_controls()
    assert snapshot["last_backtest"]["candles"] == 60


def test_chart_payload_tracks_recent_prices_and_grid():
    app.reset_simulation()
    app.engine.on_price(80_000)
    app.engine.on_price(80_100)

    snapshot = app.snapshot_with_controls()
    chart = snapshot["chart"]

    assert chart["prices"] == [80_000, 80_100]
    assert chart["last_price"] == 80_100
    assert chart["grid_lower"] == snapshot["grid"][0]
    assert chart["grid_upper"] == snapshot["grid"][-1]
    assert chart["positions"] == snapshot["positions"]
