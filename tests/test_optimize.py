import json

from botify.backtest import synthetic_closes
from botify.optimize import run_parameter_sweep, write_sweep_outputs


def test_parameter_sweep_ranks_and_writes_outputs(tmp_path):
    report = run_parameter_sweep(synthetic_closes(limit=80), source="synthetic_test")

    assert report.variants_tested > 1
    assert report.results[0].rank == 1
    assert report.results[0].score >= report.results[-1].score

    write_sweep_outputs(report, tmp_path)
    payload = json.loads((tmp_path / "sweep_report.json").read_text())
    csv_body = (tmp_path / "sweep_results.csv").read_text()

    assert payload["variants_tested"] == report.variants_tested
    assert "range_pct" in csv_body
    assert "recommendation" in csv_body
