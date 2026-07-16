# Tests

This directory contains all automated tests for the `stratos-research` project. Run the full suite with:

```bash
poetry run pytest
```

---

## `test_portfolio_config.py`

Tests for `stratos_research.portfolio_config.PortfolioConfig`.

### `TestConstruction` — Happy-path object creation

| Test | Description |
|------|-------------|
| `test_creates_with_valid_inputs` | Asserts every field is stored correctly when all inputs are valid. |
| `test_creates_with_single_asset` | Confirms a single-asset portfolio (weight = 1.0) is accepted. |
| `test_creates_with_many_assets` | Confirms a 10-asset portfolio is accepted. |
| `test_weights_sum_tolerance_accepted` | Weights that sum to 1.0 within floating-point tolerance (e.g. 1/3 × 3) are accepted. |

### `TestDateValidation` — `start_date` / `end_date` rules

| Test | Description |
|------|-------------|
| `test_raises_when_end_before_start` | `end_date` earlier than `start_date` raises `ValueError`. |
| `test_raises_when_end_equals_start` | Equal dates raise `ValueError`. |
| `test_raises_on_invalid_date_format` | A non-ISO-8601 date string raises `ValueError`. |
| `test_adjacent_days_are_valid` | A one-day window (`start + 1 day`) is accepted. |

### `TestCashValidation` — `initial_cash` rules

| Test | Description |
|------|-------------|
| `test_raises_when_initial_cash_is_zero` | Zero cash raises `ValueError`. |
| `test_raises_when_initial_cash_is_negative` | Negative cash raises `ValueError`. |
| `test_small_positive_cash_is_valid` | A very small positive value (0.01) is accepted. |

### `TestMaxDrawdownValidation` — `max_drawdown_limit` rules

| Test | Description |
|------|-------------|
| `test_raises_when_zero` | A limit of `0.0` raises `ValueError`. |
| `test_raises_when_greater_than_one` | A limit > 1.0 raises `ValueError`. |
| `test_raises_when_negative` | A negative limit raises `ValueError`. |
| `test_boundary_value_one_is_valid` | Exactly `1.0` (100 % drawdown tolerance) is accepted. |
| `test_small_fraction_is_valid` | `0.01` is accepted. |

### `TestRebalanceIntervalValidation` — `rebalance_interval_days` rules

| Test | Description |
|------|-------------|
| `test_raises_when_zero` | Zero days raises `ValueError`. |
| `test_raises_when_negative` | A negative interval raises `ValueError`. |
| `test_one_day_interval_is_valid` | An interval of `1` day is accepted. |

### `TestTargetWeightsValidation` — `target_weights` rules

| Test | Description |
|------|-------------|
| `test_raises_when_empty` | An empty dict raises `ValueError`. |
| `test_raises_when_weights_do_not_sum_to_one` | Weights summing to less than 1.0 raise `ValueError`. |
| `test_raises_when_weights_exceed_one` | Weights summing to more than 1.0 raise `ValueError`. |

### `TestMaxDriftLimitsValidation` — `max_drift_limits` rules

| Test | Description |
|------|-------------|
| `test_raises_when_keys_do_not_match_target_weights` | Mismatched ticker keys between `max_drift_limits` and `target_weights` raise `ValueError`. |
| `test_raises_when_drift_is_zero` | A drift limit of `0.0` for any ticker raises `ValueError`. |
| `test_raises_when_drift_is_negative` | A negative drift limit raises `ValueError`. |
| `test_raises_when_extra_drift_key_present` | An extra key in `max_drift_limits` not present in `target_weights` raises `ValueError`. |

### `TestGetAsJson` — `get_as_json()` serialisation

| Test | Description |
|------|-------------|
| `test_returns_valid_json_string` | The return value is a string that parses as a JSON object. |
| `test_json_contains_all_fields` | All seven configuration fields are present with correct values in the JSON output. |
| `test_json_is_round_trippable` | Parsing the JSON output and passing it back to `PortfolioConfig` produces an equal object. |
| `test_json_output_is_deterministic` | Calling `get_as_json()` twice on the same instance returns identical strings. |
