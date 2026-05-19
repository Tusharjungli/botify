from botify import app
from botify.engine import Trade


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


def test_diagnostics_and_csv_export_include_trade_data():
    app.reset_simulation()
    app.engine.state.trades.append(
        Trade(
            side="LONG",
            entry_price=80_000,
            exit_price=80_100,
            quantity=0.01,
            pnl=1.0,
            reason="target",
            opened_at="2026-01-01T00:00:00+00:00",
            closed_at="2026-01-01T00:05:00+00:00",
        )
    )
    app.engine.state.trades.append(
        Trade(
            side="SHORT",
            entry_price=80_200,
            exit_price=80_250,
            quantity=0.01,
            pnl=-0.5,
            reason="trend_flip",
            opened_at="2026-01-01T00:10:00+00:00",
            closed_at="2026-01-01T00:15:00+00:00",
        )
    )

    snapshot = app.snapshot_with_controls()
    diagnostics = snapshot["diagnostics"]
    review_notes = snapshot["review_notes"]
    csv_body = app.trades_csv()

    assert diagnostics["gross_profit"] == 1.0
    assert diagnostics["gross_loss"] == 0.5
    assert diagnostics["profit_factor"] == 2.0
    assert diagnostics["expectancy"] == 0.25
    assert diagnostics["trend_flip_exits"] == 1
    assert any(note["label"] == "Small sample" for note in review_notes)
    assert any(note["label"] == "Exposure" for note in review_notes)
    assert "side,entry_price,exit_price,quantity,pnl,reason,opened_at,closed_at" in csv_body
    assert "LONG,80000,80100,0.01,1.0,target" in csv_body
    assert "SHORT,80200,80250,0.01,-0.5,trend_flip" in csv_body


def test_cancel_orders_and_emergency_stop_controls():
    app.reset_simulation()
    app.engine.state.exchange.submit_limit_order(side="BUY", price=80_000, quantity=0.01)
    assert len(app.snapshot_with_controls()["open_orders"]) == 1

    cancel_snapshot = app.cancel_paper_orders()
    assert cancel_snapshot["open_orders"] == []
    assert "Canceled 1" in cancel_snapshot["control_message"]
    assert app.engine.state.exchange.recent_canceled()[0].status == "CANCELED"

    app.engine.state.exchange.submit_limit_order(side="SELL", price=81_000, quantity=0.01)
    stop_snapshot = app.emergency_stop()

    assert stop_snapshot["trading_enabled"] is False
    assert "Manual emergency stop" in stop_snapshot["lock_reason"]
    assert stop_snapshot["open_orders"] == []
    assert "Emergency stop active" in stop_snapshot["control_message"]


def test_runtime_is_exposed_in_snapshot_and_resets():
    app.reset_simulation()
    first = app.snapshot_with_controls()

    assert "session_started_at" in first
    assert "uptime_seconds" in first
    assert isinstance(first["uptime_seconds"], int)

    app.engine.on_price(80_000)
    second = app.snapshot_with_controls()
    assert second["uptime_seconds"] >= first["uptime_seconds"]

    app.reset_simulation()
    reset = app.snapshot_with_controls()
    assert reset["tick_count"] == 0
    assert reset["uptime_seconds"] >= 0
