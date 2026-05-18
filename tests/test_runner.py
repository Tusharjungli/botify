import subprocess
import sys


def test_cross_platform_runner_backtest_works_without_pythonpath():
    result = subprocess.run(
        [sys.executable, "run.py", "backtest", "--source", "synthetic", "--limit", "30"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Botify BTCUSDT Backtest Report" in result.stdout
    assert "Candles tested:   30" in result.stdout


def test_cross_platform_runner_help_mentions_powershell_fix():
    result = subprocess.run(
        [sys.executable, "run.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "PowerShell" in result.stdout
    assert "python run.py backtest" in result.stdout
