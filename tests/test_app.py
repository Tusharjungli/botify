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
