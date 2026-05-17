import math

from botify.backtest import interval_to_milliseconds, max_drawdown_pct, run_backtest, synthetic_closes
from botify.config import BotConfig


def test_synthetic_backtest_returns_report():
    closes = synthetic_closes(limit=120)
    report = run_backtest(closes, config=BotConfig(), interval="5m", source="synthetic")

    assert report.symbol == "BTCUSDT"
    assert report.candles == 120
    assert report.source == "synthetic"
    assert report.starting_balance == 10_000
    assert report.ending_equity > 0
    assert report.max_drawdown_pct >= 0
    assert report.closed_trades >= 0
    assert not math.isnan(report.total_return_pct)


def test_backtest_rejects_empty_prices():
    try:
        run_backtest([])
    except ValueError as exc:
        assert "at least one candle" in str(exc)
    else:
        raise AssertionError("empty backtest should fail")


def test_max_drawdown_pct():
    assert max_drawdown_pct([100, 110, 99, 120]) == 10


def test_interval_to_milliseconds_supports_common_binance_units():
    assert interval_to_milliseconds("5m") == 300_000
    assert interval_to_milliseconds("1h") == 3_600_000
    assert interval_to_milliseconds("1d") == 86_400_000
