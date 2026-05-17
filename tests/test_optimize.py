import json

from botify.backtest import synthetic_closes
from botify.optimize import SweepResult, _rank_results, run_parameter_sweep, write_sweep_outputs


def test_parameter_sweep_ranks_and_writes_outputs(tmp_path):
    report = run_parameter_sweep(synthetic_closes(limit=80), source="synthetic_test")

    assert report.variants_tested > 1
    assert report.results[0].rank == 1
    assert report.candidate_count >= 0
    assert "Candidates:" in "\n".join(report.lines())

    write_sweep_outputs(report, tmp_path)
    payload = json.loads((tmp_path / "sweep_report.json").read_text())
    csv_body = (tmp_path / "sweep_results.csv").read_text()

    assert payload["variants_tested"] == report.variants_tested
    assert payload["candidate_count"] == report.candidate_count
    assert "best_candidate" in payload
    assert "paper_session_command" in payload
    assert "range_pct" in csv_body
    assert "recommendation" in csv_body


def test_parameter_sweep_promotes_actionable_candidate_over_high_score_small_sample():
    report = run_parameter_sweep(synthetic_closes(limit=80), source="synthetic_test")
    high_score_small_sample = SweepResult(
        rank=0,
        score=99.0,
        recommendation="NEEDS_MORE_TRADES",
        range_pct=0.05,
        passive_entry_offset_steps=0.5,
        min_grid_profit_pct=0.0015,
        trailing_stop_pct=0.004,
        stop_loss_pct=0.01,
        trend_flip_min_loss_pct=0.006,
        closed_trades=14,
        total_return_pct=0.05,
        ending_equity=10_005,
        profit_factor=1.95,
        win_rate=70.0,
        max_drawdown_pct=0.03,
        realized_pnl=5.0,
        biggest_loss=-1.0,
    )
    lower_score_candidate = SweepResult(
        rank=0,
        score=40.0,
        recommendation="CANDIDATE_FOR_PAPER_TEST",
        range_pct=0.035,
        passive_entry_offset_steps=0.35,
        min_grid_profit_pct=0.0015,
        trailing_stop_pct=0.004,
        stop_loss_pct=0.01,
        trend_flip_min_loss_pct=0.006,
        closed_trades=48,
        total_return_pct=0.04,
        ending_equity=10_004,
        profit_factor=1.36,
        win_rate=55.0,
        max_drawdown_pct=0.07,
        realized_pnl=4.0,
        biggest_loss=-2.0,
    )
    ranked = _rank_results([high_score_small_sample, lower_score_candidate])
    actionable_report = type(report)(
        source="binance_public",
        interval="1m",
        candles=5000,
        variants_tested=2,
        results=ranked,
    )

    assert actionable_report.results[0].recommendation == "CANDIDATE_FOR_PAPER_TEST"
    assert actionable_report.best_candidate == actionable_report.results[0]
    assert actionable_report.candidate_count == 1
    body = "\n".join(actionable_report.lines(limit=2))
    assert "Best paper-test candidates:" in body
    assert "Next paper-session command:" in body
    assert "--range-pct 0.035" in actionable_report.paper_session_command()
