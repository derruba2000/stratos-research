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

---

## `test_sqlite_data_engine.py`

Tests for `stratos_research.data_engine.SQLiteDataEngine` and `InMemorySource`.

The suite builds a temporary SQLite database with `securities` and `price_history` tables so the tests stay isolated from the local production-sized database at `/Users/joaoramo/Data/trading_experiment/portfolio_management.sqlite3`.

### `TestLoadDailyPrices` — SQLite extraction and DataFrame formatting

| Test | Description |
|------|-------------|
| `test_loads_requested_tickers_inside_date_range` | Confirms only requested symbols and inclusive date-range rows are returned. |
| `test_returns_pybroker_shaped_columns` | Verifies the output columns are `symbol`, `date`, `open`, `high`, `low`, `close`, and `volume`. |
| `test_converts_dates_and_numeric_values` | Ensures `date` is converted to a datetime dtype and OHLCV values are numeric floats. |
| `test_accepts_date_objects` | Confirms `datetime.date` inputs are accepted as well as ISO date strings. |
| `test_returns_empty_dataframe_with_expected_schema` | Missing tickers return an empty DataFrame with the expected schema. |
| `test_raises_when_tickers_are_empty` | An empty ticker list raises `ValueError`. |
| `test_raises_when_end_date_is_before_start_date` | An end date before the start date raises `ValueError`. |
| `test_raises_when_database_does_not_exist` | A missing SQLite database path raises `FileNotFoundError`. |

### `TestLoadAlignedDailyPrices` — Multi-asset timeline synchronization

| Test | Description |
|------|-------------|
| `test_fills_missing_dates_with_last_available_bar` | Expands mixed asset calendars onto a shared daily timeline and forward-fills each ticker from its last known bar. |
| `test_forward_filled_rows_use_zero_volume` | Synthetic forward-filled rows preserve the last close and set volume to `0.0`. |
| `test_drops_dates_before_every_requested_symbol_has_prices` | Dates before all requested symbols have at least one known price are excluded from the aligned matrix. |
| `test_returns_empty_when_any_requested_symbol_never_has_prices` | If any requested ticker has no historical bars, alignment returns an empty DataFrame with the expected schema. |

### `TestCreateInMemorySource` — In-memory source creation

| Test | Description |
|------|-------------|
| `test_creates_source_from_aligned_prices_by_default` | Confirms `create_in_memory_source()` wraps an aligned, gap-free price DataFrame by default. |
| `test_can_create_source_from_unaligned_loaded_prices` | Confirms callers can opt out of timeline alignment and keep raw loaded bars. |
| `test_source_returns_defensive_dataframe_copy` | Verifies `to_dataframe()` returns a defensive copy rather than exposing mutable internal state. |

### `TestCompatibilityAliases` — UML method aliases

| Test | Description |
|------|-------------|
| `test_load_daily_prices_camel_case_alias` | Confirms `loadDailyPrices()` delegates to `load_daily_prices()`. |
| `test_create_in_memory_source_camel_case_alias` | Confirms `createInMemorySource()` delegates to `create_in_memory_source()`. |

### `TestEnvironmentConfiguration` — `.env` database path loading

| Test | Description |
|------|-------------|
| `test_get_sqlite_db_path_reads_existing_environment_variable` | Confirms `SQLITE_DB_PATH` can be read directly from the process environment. |
| `test_get_sqlite_db_path_loads_dotenv_file` | Confirms `SQLITE_DB_PATH` is loaded from a `.env` file when it is not already set. |
| `test_load_env_file_does_not_override_existing_value_by_default` | Ensures shell-provided environment values take precedence over `.env` values. |
| `test_engine_from_env_uses_configured_database_path` | Confirms `SQLiteDataEngine.from_env()` builds an engine from a `.env` file. |
| `test_engine_constructor_defaults_to_environment_path` | Confirms `SQLiteDataEngine()` uses `SQLITE_DB_PATH` when no explicit database path is provided. |
| `test_get_sqlite_db_path_raises_when_unconfigured` | Missing environment configuration raises `EnvironmentError`. |

---

## `test_pybroker_rebalance_engine.py`

Tests for `stratos_research.pybroker_engine.PyBrokerRebalanceEngine`.

The suite uses synthetic two-symbol OHLCV data so the PyBroker strategy loop and indicator pipeline can be exercised without depending on the local SQLite database.

### `TestIndicatorFunctions` — Momentum indicator calculations

| Test | Description |
|------|-------------|
| `test_rsi_indicator_returns_one_value_per_bar` | Confirms the 14-day RSI function returns one value per bar and reaches `100.0` for a strictly rising series. |
| `test_macd_indicators_return_one_value_per_bar` | Confirms MACD, signal, and histogram arrays are aligned to the input bar count. |

### `TestPyBrokerRebalanceEngine` — PyBroker strategy execution

| Test | Description |
|------|-------------|
| `test_register_indicators_creates_rsi_and_macd_pipeline` | Registers RSI, MACD, MACD signal, and MACD histogram indicators. |
| `test_run_backtest_returns_pybroker_test_result` | Runs PyBroker over an `InMemorySource` and returns a populated `TestResult`. |
| `test_run_backtest_invokes_after_exec_hook_with_indicators` | Verifies the `set_after_exec` hook receives contexts with finite indicator values after bootstrap. |
| `test_camel_case_aliases_match_class_diagram` | Confirms `registerIndicators()` and `runBacktest()` delegate to their Pythonic methods. |
