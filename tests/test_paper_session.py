from pathlib import Path
import json

from botify.paper_session import run_paper_session


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
