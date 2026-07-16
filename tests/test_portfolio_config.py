import json

import pytest

from stratos_research.portfolio_config import PortfolioConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_KWARGS = dict(
    start_date="2023-01-01",
    end_date="2024-01-01",
    initial_cash=100_000.0,
    max_drawdown_limit=0.15,
    rebalance_interval_days=30,
    target_weights={"AAPL": 0.5, "MSFT": 0.5},
    max_drift_limits={"AAPL": 0.05, "MSFT": 0.05},
)


def make_config(**overrides) -> PortfolioConfig:
    return PortfolioConfig(**{**VALID_KWARGS, **overrides})


# ---------------------------------------------------------------------------
# Construction — happy path
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_with_valid_inputs(self):
        cfg = make_config()
        assert cfg.start_date == "2023-01-01"
        assert cfg.end_date == "2024-01-01"
        assert cfg.initial_cash == 100_000.0
        assert cfg.max_drawdown_limit == 0.15
        assert cfg.rebalance_interval_days == 30
        assert cfg.target_weights == {"AAPL": 0.5, "MSFT": 0.5}
        assert cfg.max_drift_limits == {"AAPL": 0.05, "MSFT": 0.05}

    def test_creates_with_single_asset(self):
        cfg = make_config(
            target_weights={"SPY": 1.0},
            max_drift_limits={"SPY": 0.02},
        )
        assert cfg.target_weights == {"SPY": 1.0}

    def test_creates_with_many_assets(self):
        weights = {f"TICKER{i}": 0.1 for i in range(10)}
        drifts = {f"TICKER{i}": 0.05 for i in range(10)}
        cfg = make_config(target_weights=weights, max_drift_limits=drifts)
        assert len(cfg.target_weights) == 10

    def test_weights_sum_tolerance_accepted(self):
        # Weights that sum to exactly 1.0 within floating-point tolerance
        weights = {"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}
        drifts = {"A": 0.05, "B": 0.05, "C": 0.05}
        cfg = make_config(target_weights=weights, max_drift_limits=drifts)
        assert set(cfg.target_weights) == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------


class TestDateValidation:
    def test_raises_when_end_before_start(self):
        with pytest.raises(ValueError, match="end_date.*must be after"):
            make_config(start_date="2024-01-01", end_date="2023-01-01")

    def test_raises_when_end_equals_start(self):
        with pytest.raises(ValueError, match="end_date.*must be after"):
            make_config(start_date="2023-06-01", end_date="2023-06-01")

    def test_raises_on_invalid_date_format(self):
        with pytest.raises(ValueError):
            make_config(start_date="01-01-2023")

    def test_adjacent_days_are_valid(self):
        cfg = make_config(start_date="2023-01-01", end_date="2023-01-02")
        assert cfg.start_date == "2023-01-01"


# ---------------------------------------------------------------------------
# Cash validation
# ---------------------------------------------------------------------------


class TestCashValidation:
    def test_raises_when_initial_cash_is_zero(self):
        with pytest.raises(ValueError, match="initial_cash must be positive"):
            make_config(initial_cash=0)

    def test_raises_when_initial_cash_is_negative(self):
        with pytest.raises(ValueError, match="initial_cash must be positive"):
            make_config(initial_cash=-500.0)

    def test_small_positive_cash_is_valid(self):
        cfg = make_config(initial_cash=0.01)
        assert cfg.initial_cash == 0.01


# ---------------------------------------------------------------------------
# Max drawdown limit validation
# ---------------------------------------------------------------------------


class TestMaxDrawdownValidation:
    def test_raises_when_zero(self):
        with pytest.raises(ValueError, match="max_drawdown_limit"):
            make_config(max_drawdown_limit=0.0)

    def test_raises_when_greater_than_one(self):
        with pytest.raises(ValueError, match="max_drawdown_limit"):
            make_config(max_drawdown_limit=1.1)

    def test_raises_when_negative(self):
        with pytest.raises(ValueError, match="max_drawdown_limit"):
            make_config(max_drawdown_limit=-0.1)

    def test_boundary_value_one_is_valid(self):
        cfg = make_config(max_drawdown_limit=1.0)
        assert cfg.max_drawdown_limit == 1.0

    def test_small_fraction_is_valid(self):
        cfg = make_config(max_drawdown_limit=0.01)
        assert cfg.max_drawdown_limit == 0.01


# ---------------------------------------------------------------------------
# Rebalance interval validation
# ---------------------------------------------------------------------------


class TestRebalanceIntervalValidation:
    def test_raises_when_zero(self):
        with pytest.raises(ValueError, match="rebalance_interval_days"):
            make_config(rebalance_interval_days=0)

    def test_raises_when_negative(self):
        with pytest.raises(ValueError, match="rebalance_interval_days"):
            make_config(rebalance_interval_days=-1)

    def test_one_day_interval_is_valid(self):
        cfg = make_config(rebalance_interval_days=1)
        assert cfg.rebalance_interval_days == 1


# ---------------------------------------------------------------------------
# Target weights validation
# ---------------------------------------------------------------------------


class TestTargetWeightsValidation:
    def test_raises_when_empty(self):
        with pytest.raises(ValueError, match="target_weights must not be empty"):
            make_config(target_weights={}, max_drift_limits={})

    def test_raises_when_weights_do_not_sum_to_one(self):
        with pytest.raises(ValueError, match="target_weights must sum to 1.0"):
            make_config(
                target_weights={"AAPL": 0.4, "MSFT": 0.4},
                max_drift_limits={"AAPL": 0.05, "MSFT": 0.05},
            )

    def test_raises_when_weights_exceed_one(self):
        with pytest.raises(ValueError, match="target_weights must sum to 1.0"):
            make_config(
                target_weights={"AAPL": 0.6, "MSFT": 0.6},
                max_drift_limits={"AAPL": 0.05, "MSFT": 0.05},
            )


# ---------------------------------------------------------------------------
# Max drift limits validation
# ---------------------------------------------------------------------------


class TestMaxDriftLimitsValidation:
    def test_raises_when_keys_do_not_match_target_weights(self):
        with pytest.raises(ValueError, match="max_drift_limits keys must match"):
            make_config(
                target_weights={"AAPL": 0.5, "MSFT": 0.5},
                max_drift_limits={"AAPL": 0.05, "GOOG": 0.05},
            )

    def test_raises_when_drift_is_zero(self):
        with pytest.raises(ValueError, match="max_drift_limits"):
            make_config(
                target_weights={"AAPL": 0.5, "MSFT": 0.5},
                max_drift_limits={"AAPL": 0.0, "MSFT": 0.05},
            )

    def test_raises_when_drift_is_negative(self):
        with pytest.raises(ValueError, match="max_drift_limits"):
            make_config(
                target_weights={"AAPL": 0.5, "MSFT": 0.5},
                max_drift_limits={"AAPL": -0.01, "MSFT": 0.05},
            )

    def test_raises_when_extra_drift_key_present(self):
        with pytest.raises(ValueError, match="max_drift_limits keys must match"):
            make_config(
                target_weights={"AAPL": 1.0},
                max_drift_limits={"AAPL": 0.05, "MSFT": 0.05},
            )


# ---------------------------------------------------------------------------
# get_as_json
# ---------------------------------------------------------------------------


class TestGetAsJson:
    def test_returns_valid_json_string(self):
        cfg = make_config()
        result = cfg.get_as_json()
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_contains_all_fields(self):
        cfg = make_config()
        parsed = json.loads(cfg.get_as_json())
        assert parsed["start_date"] == "2023-01-01"
        assert parsed["end_date"] == "2024-01-01"
        assert parsed["initial_cash"] == 100_000.0
        assert parsed["max_drawdown_limit"] == 0.15
        assert parsed["rebalance_interval_days"] == 30
        assert parsed["target_weights"] == {"AAPL": 0.5, "MSFT": 0.5}
        assert parsed["max_drift_limits"] == {"AAPL": 0.05, "MSFT": 0.05}

    def test_json_is_round_trippable(self):
        cfg = make_config()
        parsed = json.loads(cfg.get_as_json())
        restored = PortfolioConfig(**parsed)
        assert restored == cfg

    def test_json_output_is_deterministic(self):
        cfg = make_config()
        assert cfg.get_as_json() == cfg.get_as_json()
