import json
from dataclasses import dataclass, field
from datetime import date


@dataclass
class PortfolioConfig:
    """Unified configuration container for a single backtest instance.

    Encapsulates all rules, risk constraints, and asset-weight definitions
    that drive the rebalancing engine. Serves as the single source of truth
    for a given simulation run.
    """

    start_date: str
    end_date: str
    initial_cash: float
    max_drawdown_limit: float
    rebalance_interval_days: int
    target_weights: dict[str, float]
    max_drift_limits: dict[str, float]

    def __post_init__(self) -> None:
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)

        if end <= start:
            raise ValueError(
                f"end_date ({self.end_date}) must be after start_date ({self.start_date})"
            )

        if self.initial_cash <= 0:
            raise ValueError(f"initial_cash must be positive, got {self.initial_cash}")

        if not (0 < self.max_drawdown_limit <= 1):
            raise ValueError(
                f"max_drawdown_limit must be in (0, 1], got {self.max_drawdown_limit}"
            )

        if self.rebalance_interval_days < 1:
            raise ValueError(
                f"rebalance_interval_days must be >= 1, got {self.rebalance_interval_days}"
            )

        if not self.target_weights:
            raise ValueError("target_weights must not be empty")

        total_weight = sum(self.target_weights.values())
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(
                f"target_weights must sum to 1.0, got {total_weight:.6f}"
            )

        if set(self.max_drift_limits) != set(self.target_weights):
            raise ValueError(
                "max_drift_limits keys must match target_weights keys"
            )

        for ticker, drift in self.max_drift_limits.items():
            if drift <= 0:
                raise ValueError(
                    f"max_drift_limits['{ticker}'] must be positive, got {drift}"
                )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def get_as_json(self) -> str:
        """Serialise the configuration to a JSON string for database storage."""
        return json.dumps(
            {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "initial_cash": self.initial_cash,
                "max_drawdown_limit": self.max_drawdown_limit,
                "rebalance_interval_days": self.rebalance_interval_days,
                "target_weights": self.target_weights,
                "max_drift_limits": self.max_drift_limits,
            }
        )
