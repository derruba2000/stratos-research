from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd
from pybroker import Strategy, StrategyConfig, indicator
from pybroker.indicator import Indicator
from pybroker.strategy import TestResult

from stratos_research.data_engine import InMemorySource
from stratos_research.portfolio_config import PortfolioConfig


RSI_INDICATOR_NAME = "stratos_rsi_14"
MACD_INDICATOR_NAME = "stratos_macd"
MACD_SIGNAL_INDICATOR_NAME = "stratos_macd_signal"
MACD_HISTOGRAM_INDICATOR_NAME = "stratos_macd_histogram"


@dataclass
class PyBrokerRebalanceEngine:
    """Core PyBroker simulation and indicator pipeline."""

    config: PortfolioConfig
    bootstrap_bars: int = 30
    pybroker_strategy: Strategy | None = field(default=None, init=False)
    indicators: list[Indicator] = field(default_factory=list, init=False)
    hook_snapshots: list[dict[str, dict[str, float]]] = field(
        default_factory=list,
        init=False,
    )

    def register_indicators(self) -> None:
        """Register RSI and MACD indicators with PyBroker."""
        self.indicators = [
            indicator(RSI_INDICATOR_NAME, _rsi_indicator, period=14),
            indicator(MACD_INDICATOR_NAME, _macd_indicator),
            indicator(MACD_SIGNAL_INDICATOR_NAME, _macd_signal_indicator),
            indicator(MACD_HISTOGRAM_INDICATOR_NAME, _macd_histogram_indicator),
        ]

    def run_backtest(self, source: InMemorySource) -> TestResult:
        """Run the configured PyBroker backtest over an in-memory data source."""
        if not self.indicators:
            self.register_indicators()

        data = source.to_dataframe()
        symbols = list(self.config.target_weights)
        strategy_config = StrategyConfig(initial_cash=self.config.initial_cash)
        self.pybroker_strategy = Strategy(
            data,
            self.config.start_date,
            self.config.end_date,
            strategy_config,
        )
        self.pybroker_strategy.add_execution(
            self._execution_hook,
            symbols,
            indicators=self.indicators,
        )
        self.pybroker_strategy.set_after_exec(self.reallocate_portfolio_hook)

        return self.pybroker_strategy.backtest(warmup=self.bootstrap_bars)

    def reallocate_portfolio_hook(self, ctxs: Mapping) -> None:
        """Run after every PyBroker bar once all symbol executions complete."""
        self.hook_snapshots.append(self._indicator_snapshot(ctxs))
        self._check_drawdown_circuit_breaker(ctxs)
        self._evaluate_drift_and_interval(ctxs)

    def registerIndicators(self) -> None:
        """Compatibility alias for the UML class spec."""
        self.register_indicators()

    def runBacktest(self, source: InMemorySource) -> TestResult:
        """Compatibility alias for the UML class spec."""
        return self.run_backtest(source)

    def reallocatePortfolioHook(self, ctxs: Mapping) -> None:
        """Compatibility alias for the UML class spec."""
        self.reallocate_portfolio_hook(ctxs)

    def _execution_hook(self, ctx) -> None:
        """Keep registered indicators attached to each symbol context."""
        for registered_indicator in self.indicators:
            ctx.indicator(registered_indicator.name)

    def _indicator_snapshot(self, ctxs: Mapping) -> dict[str, dict[str, float]]:
        snapshot = {}

        for symbol, ctx in ctxs.items():
            snapshot[symbol] = {
                RSI_INDICATOR_NAME: _last_finite(ctx.indicator(RSI_INDICATOR_NAME)),
                MACD_INDICATOR_NAME: _last_finite(ctx.indicator(MACD_INDICATOR_NAME)),
                MACD_SIGNAL_INDICATOR_NAME: _last_finite(
                    ctx.indicator(MACD_SIGNAL_INDICATOR_NAME)
                ),
                MACD_HISTOGRAM_INDICATOR_NAME: _last_finite(
                    ctx.indicator(MACD_HISTOGRAM_INDICATOR_NAME)
                ),
            }

        return snapshot

    def _check_drawdown_circuit_breaker(self, ctxs: Mapping) -> bool:
        """Epic 3 placeholder for portfolio-level drawdown enforcement."""
        return False

    def _evaluate_drift_and_interval(self, ctxs: Mapping) -> bool:
        """Epic 3 placeholder for drift and rebalance interval logic."""
        return False


def _rsi_indicator(bar_data, period: int = 14) -> np.ndarray:
    close = _as_float_series(bar_data.close)
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return rsi.to_numpy(dtype=np.float64)


def _macd_indicator(bar_data) -> np.ndarray:
    close = _as_float_series(bar_data.close)
    return _macd_line(close).to_numpy(dtype=np.float64)


def _macd_signal_indicator(bar_data) -> np.ndarray:
    close = _as_float_series(bar_data.close)
    signal = _macd_line(close).ewm(span=9, adjust=False).mean()
    return signal.to_numpy(dtype=np.float64)


def _macd_histogram_indicator(bar_data) -> np.ndarray:
    close = _as_float_series(bar_data.close)
    macd = _macd_line(close)
    signal = macd.ewm(span=9, adjust=False).mean()
    return (macd - signal).to_numpy(dtype=np.float64)


def _macd_line(close: pd.Series) -> pd.Series:
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    return fast - slow


def _as_float_series(values) -> pd.Series:
    return pd.Series(values, dtype="float64")


def _last_finite(values) -> float:
    finite_values = pd.Series(values, dtype="float64").dropna()
    if finite_values.empty:
        return float("nan")

    return float(finite_values.iloc[-1])
