from argparse import Namespace
from pathlib import Path
import json

from botify.paper_session import _recommendation, build_config_from_args, run_paper_session


def test_paper_session_writes_report_snapshot_and_trades(tmp_path):
    report = run_paper_session(
        ticks=80,
        target_closed_trades=1,
        source="synthetic",
        sleep_seconds=0,
        save_every=10,
        output_dir=tmp_path,
    )

    session_dir = Path(report.output_dir)
    assert session_dir.exists()
    assert (session_dir / "report.json").exists()
    assert (session_dir / "latest_snapshot.json").exists()
    assert (session_dir / "trades.csv").exists()

    payload = json.loads((session_dir / "report.json").read_text())
    snapshot = json.loads((session_dir / "latest_snapshot.json").read_text())
    trades_csv = (session_dir / "trades.csv").read_text()

    assert payload["symbol"] == "BTCUSDT"
    assert payload["source"] == "synthetic"
    assert payload["ticks"] == snapshot["tick_count"]
    assert "recommendation" in payload
    assert "side,entry_price,exit_price,quantity,pnl,reason,opened_at,closed_at" in trades_csv


def test_paper_session_replays_synthetic_candles(tmp_path):
    report = run_paper_session(
        ticks=80,
        target_closed_trades=1,
        source="synthetic-candles",
        interval="5m",
        sleep_seconds=0,
        save_every=20,
        output_dir=tmp_path,
    )

    assert report.source == "synthetic_5m_candles"
    assert 1 <= report.ticks <= 80


def test_paper_session_rejects_losing_diagnostic_sample_before_target():
    recommendation = _recommendation(
        closed_trades=29,
        target_closed_trades=100,
        ending_equity=9_947.22,
        starting_balance=10_000,
        profit_factor=0.32,
        expectancy=-1.77,
        lock_reason="",
    )

    assert recommendation.startswith("REJECT_CANDIDATE")


def test_paper_session_config_overrides_match_optimizer_candidate():
    config = build_config_from_args(
        Namespace(
            range_pct=0.035,
            entry_offset=0.5,
            min_grid_profit_pct=0.0015,
            trailing_stop_pct=0.004,
            stop_loss_pct=0.01,
            trend_flip_min_loss_pct=0.006,
        )
    )

    assert config.range_pct == 0.035
    assert config.passive_entry_offset_steps == 0.5
    assert config.min_grid_profit_pct == 0.0015
    assert config.trailing_stop_pct == 0.004
    assert config.stop_loss_pct == 0.01
    assert config.trend_flip_min_loss_pct == 0.006
