import numpy as np
import pandas as pd

from pybroker.strategy import TestResult as PyBrokerTestResult

from stratos_research.data_engine import InMemorySource
from stratos_research.portfolio_config import PortfolioConfig
from stratos_research.pybroker_engine import (
    MACD_HISTOGRAM_INDICATOR_NAME,
    MACD_INDICATOR_NAME,
    MACD_SIGNAL_INDICATOR_NAME,
    RSI_INDICATOR_NAME,
    PyBrokerRebalanceEngine,
    _macd_histogram_indicator,
    _macd_indicator,
    _macd_signal_indicator,
    _rsi_indicator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(**overrides) -> PortfolioConfig:
    kwargs = {
        "start_date": "2024-01-01",
        "end_date": "2024-02-29",
        "initial_cash": 100_000.0,
        "max_drawdown_limit": 0.2,
        "rebalance_interval_days": 14,
        "target_weights": {"AAPL": 0.5, "MSFT": 0.5},
        "max_drift_limits": {"AAPL": 0.05, "MSFT": 0.05},
    }
    kwargs.update(overrides)
    return PortfolioConfig(**kwargs)


def make_source() -> InMemorySource:
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    rows = []

    for symbol, base_price in [("AAPL", 100.0), ("MSFT", 200.0)]:
        for index, current_date in enumerate(dates):
            close = base_price + index
            rows.append(
                {
                    "symbol": symbol,
                    "date": current_date,
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1000.0 + index,
                }
            )

    return InMemorySource(pd.DataFrame(rows))


class BarDataStub:
    def __init__(self, close):
        self.close = np.array(close, dtype=np.float64)


# ---------------------------------------------------------------------------
# Indicator functions
# ---------------------------------------------------------------------------


class TestIndicatorFunctions:
    def test_rsi_indicator_returns_one_value_per_bar(self):
        result = _rsi_indicator(BarDataStub(np.arange(1, 41)))

        assert len(result) == 40
        assert result[-1] == 100.0

    def test_macd_indicators_return_one_value_per_bar(self):
        bars = BarDataStub(np.arange(1, 41))

        macd = _macd_indicator(bars)
        signal = _macd_signal_indicator(bars)
        histogram = _macd_histogram_indicator(bars)

        assert len(macd) == 40
        assert len(signal) == 40
        assert len(histogram) == 40
        assert histogram[-1] == macd[-1] - signal[-1]


# ---------------------------------------------------------------------------
# PyBrokerRebalanceEngine
# ---------------------------------------------------------------------------


class TestPyBrokerRebalanceEngine:
    def test_register_indicators_creates_rsi_and_macd_pipeline(self):
        engine = PyBrokerRebalanceEngine(make_config())

        engine.register_indicators()

        assert [indicator.name for indicator in engine.indicators] == [
            RSI_INDICATOR_NAME,
            MACD_INDICATOR_NAME,
            MACD_SIGNAL_INDICATOR_NAME,
            MACD_HISTOGRAM_INDICATOR_NAME,
        ]

    def test_run_backtest_returns_pybroker_test_result(self):
        engine = PyBrokerRebalanceEngine(make_config())

        result = engine.run_backtest(make_source())

        assert isinstance(result, PyBrokerTestResult)
        assert not result.portfolio.empty
        assert engine.pybroker_strategy is not None

    def test_run_backtest_invokes_after_exec_hook_with_indicators(self):
        engine = PyBrokerRebalanceEngine(make_config())

        engine.run_backtest(make_source())

        assert engine.hook_snapshots
        latest = engine.hook_snapshots[-1]
        assert set(latest) == {"AAPL", "MSFT"}
        assert np.isfinite(latest["AAPL"][RSI_INDICATOR_NAME])
        assert np.isfinite(latest["AAPL"][MACD_INDICATOR_NAME])
        assert np.isfinite(latest["AAPL"][MACD_SIGNAL_INDICATOR_NAME])
        assert np.isfinite(latest["AAPL"][MACD_HISTOGRAM_INDICATOR_NAME])

    def test_camel_case_aliases_match_class_diagram(self):
        engine = PyBrokerRebalanceEngine(make_config())

        engine.registerIndicators()
        result = engine.runBacktest(make_source())

        assert isinstance(result, PyBrokerTestResult)
        assert engine.indicators
