import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from stratos_research.data_engine import InMemorySource, SQLiteDataEngine
from stratos_research.data_engine import get_sqlite_db_path, load_env_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_price_database(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE securities (
                id INTEGER NOT NULL,
                ticker VARCHAR(32) NOT NULL,
                name VARCHAR(255) NOT NULL,
                asset_class VARCHAR(11) NOT NULL,
                currency_code VARCHAR(3) NOT NULL,
                PRIMARY KEY (id),
                UNIQUE (ticker)
            );

            CREATE TABLE price_history (
                security_id INTEGER NOT NULL,
                symbol VARCHAR(32),
                date DATE NOT NULL,
                open NUMERIC(32, 10),
                high NUMERIC(32, 10),
                low NUMERIC(32, 10),
                close NUMERIC(32, 10) NOT NULL,
                volume NUMERIC(32, 10),
                PRIMARY KEY (security_id, date),
                FOREIGN KEY(security_id) REFERENCES securities (id)
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO securities (
                id, ticker, name, asset_class, currency_code
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "AAPL", "Apple Inc.", "EQUITY", "USD"),
                (2, "MSFT", "Microsoft Corp.", "EQUITY", "USD"),
                (3, "GOOG", "Alphabet Inc.", "EQUITY", "USD"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO price_history (
                security_id, symbol, date, open, high, low, close, volume
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "AAPL", "2024-01-01", 100, 110, 95, 105, 1000),
                (1, "AAPL", "2024-01-02", 105, 112, 101, 108, 1200),
                (2, "MSFT", "2024-01-01", 200, 210, 198, 205, 1500),
                (2, "MSFT", "2024-01-03", 205, 215, 202, 212, 1700),
                (3, "GOOG", "2024-01-01", 300, 320, 290, 310, 900),
            ],
        )


@pytest.fixture
def price_db_path(tmp_path):
    db_path = tmp_path / "portfolio_management.sqlite3"
    create_price_database(db_path)
    return db_path


# ---------------------------------------------------------------------------
# load_daily_prices
# ---------------------------------------------------------------------------


class TestLoadDailyPrices:
    def test_loads_requested_tickers_inside_date_range(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_daily_prices(
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-02",
        )

        assert result["symbol"].tolist() == ["AAPL", "MSFT", "AAPL"]
        assert result["close"].tolist() == [105.0, 205.0, 108.0]

    def test_returns_pybroker_shaped_columns(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_daily_prices(["AAPL"], "2024-01-01", "2024-01-02")

        assert result.columns.tolist() == [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

    def test_converts_dates_and_numeric_values(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_daily_prices(["AAPL"], "2024-01-01", "2024-01-01")

        assert pd.api.types.is_datetime64_any_dtype(result["date"])
        assert pd.api.types.is_float_dtype(result["open"])
        assert pd.api.types.is_float_dtype(result["close"])

    def test_accepts_date_objects(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_daily_prices(
            ["AAPL"],
            date(2024, 1, 1),
            date(2024, 1, 2),
        )

        assert len(result) == 2

    def test_returns_empty_dataframe_with_expected_schema(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_daily_prices(["TSLA"], "2024-01-01", "2024-01-02")

        assert result.empty
        assert result.columns.tolist() == [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

    def test_raises_when_tickers_are_empty(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        with pytest.raises(ValueError, match="tickers must not be empty"):
            engine.load_daily_prices([], "2024-01-01", "2024-01-02")

    def test_raises_when_end_date_is_before_start_date(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        with pytest.raises(ValueError, match="end .* must be on or after start"):
            engine.load_daily_prices(["AAPL"], "2024-01-02", "2024-01-01")

    def test_raises_when_database_does_not_exist(self, tmp_path):
        engine = SQLiteDataEngine(tmp_path / "missing.sqlite3")

        with pytest.raises(FileNotFoundError, match="SQLite database not found"):
            engine.load_daily_prices(["AAPL"], "2024-01-01", "2024-01-02")


# ---------------------------------------------------------------------------
# load_aligned_daily_prices
# ---------------------------------------------------------------------------


class TestLoadAlignedDailyPrices:
    def test_fills_missing_dates_with_last_available_bar(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_aligned_daily_prices(
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-03",
        )

        assert result["date"].dt.strftime("%Y-%m-%d").tolist() == [
            "2024-01-01",
            "2024-01-01",
            "2024-01-02",
            "2024-01-02",
            "2024-01-03",
            "2024-01-03",
        ]
        assert result["symbol"].tolist() == [
            "AAPL",
            "MSFT",
            "AAPL",
            "MSFT",
            "AAPL",
            "MSFT",
        ]

    def test_forward_filled_rows_use_zero_volume(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_aligned_daily_prices(
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-03",
        )
        msft_missing_day = result[
            (result["symbol"] == "MSFT")
            & (result["date"] == pd.Timestamp("2024-01-02"))
        ].iloc[0]
        aapl_missing_day = result[
            (result["symbol"] == "AAPL")
            & (result["date"] == pd.Timestamp("2024-01-03"))
        ].iloc[0]

        assert msft_missing_day["close"] == 205.0
        assert msft_missing_day["volume"] == 0.0
        assert aapl_missing_day["close"] == 108.0
        assert aapl_missing_day["volume"] == 0.0

    def test_drops_dates_before_every_requested_symbol_has_prices(self):
        raw_prices = pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "date": "2024-01-01",
                    "open": 100,
                    "high": 110,
                    "low": 95,
                    "close": 105,
                    "volume": 1000,
                },
                {
                    "symbol": "MSFT",
                    "date": "2024-01-03",
                    "open": 200,
                    "high": 210,
                    "low": 198,
                    "close": 205,
                    "volume": 1500,
                },
            ]
        )

        result = SQLiteDataEngine.align_daily_prices(
            raw_prices,
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-03",
        )

        assert result["date"].dt.strftime("%Y-%m-%d").tolist() == [
            "2024-01-03",
            "2024-01-03",
        ]
        assert result["symbol"].tolist() == ["AAPL", "MSFT"]

    def test_returns_empty_when_any_requested_symbol_never_has_prices(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.load_aligned_daily_prices(
            ["AAPL", "TSLA"],
            "2024-01-01",
            "2024-01-03",
        )

        assert result.empty
        assert result.columns.tolist() == [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]


# ---------------------------------------------------------------------------
# create_in_memory_source
# ---------------------------------------------------------------------------


class TestCreateInMemorySource:
    def test_creates_source_from_aligned_prices_by_default(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        source = engine.create_in_memory_source(
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-03",
        )

        assert isinstance(source, InMemorySource)
        assert len(source.data) == 6

    def test_can_create_source_from_unaligned_loaded_prices(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        source = engine.create_in_memory_source(
            ["AAPL", "MSFT"],
            "2024-01-01",
            "2024-01-03",
            align_timelines=False,
        )

        assert source.data["symbol"].tolist() == ["AAPL", "MSFT", "AAPL", "MSFT"]

    def test_source_returns_defensive_dataframe_copy(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)
        source = engine.create_in_memory_source(
            ["AAPL"],
            "2024-01-01",
            "2024-01-01",
        )

        copied = source.to_dataframe()
        copied.loc[0, "close"] = 0

        assert source.data.loc[0, "close"] == 105.0


# ---------------------------------------------------------------------------
# UML compatibility aliases
# ---------------------------------------------------------------------------


class TestCompatibilityAliases:
    def test_load_daily_prices_camel_case_alias(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        result = engine.loadDailyPrices(["AAPL"], "2024-01-01", "2024-01-01")

        assert result["symbol"].tolist() == ["AAPL"]

    def test_create_in_memory_source_camel_case_alias(self, price_db_path):
        engine = SQLiteDataEngine(price_db_path)

        source = engine.createInMemorySource(["AAPL"], "2024-01-01", "2024-01-01")

        assert isinstance(source, InMemorySource)


# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------


class TestEnvironmentConfiguration:
    def test_get_sqlite_db_path_reads_existing_environment_variable(
        self,
        monkeypatch,
        price_db_path,
    ):
        monkeypatch.setenv("SQLITE_DB_PATH", str(price_db_path))

        assert get_sqlite_db_path() == price_db_path

    def test_get_sqlite_db_path_loads_dotenv_file(
        self,
        monkeypatch,
        tmp_path,
        price_db_path,
    ):
        monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text(f"SQLITE_DB_PATH={price_db_path}\n")

        assert get_sqlite_db_path(env_path) == price_db_path

    def test_load_env_file_does_not_override_existing_value_by_default(
        self,
        monkeypatch,
        tmp_path,
        price_db_path,
    ):
        monkeypatch.setenv("SQLITE_DB_PATH", "/already/configured.sqlite3")
        env_path = tmp_path / ".env"
        env_path.write_text(f"SQLITE_DB_PATH={price_db_path}\n")

        load_env_file(env_path)

        assert get_sqlite_db_path(env_path) == Path("/already/configured.sqlite3")

    def test_engine_from_env_uses_configured_database_path(
        self,
        monkeypatch,
        tmp_path,
        price_db_path,
    ):
        monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
        env_path = tmp_path / ".env"
        env_path.write_text(f"SQLITE_DB_PATH={price_db_path}\n")

        engine = SQLiteDataEngine.from_env(env_path)

        assert engine.db_path == price_db_path

    def test_engine_constructor_defaults_to_environment_path(
        self,
        monkeypatch,
        price_db_path,
    ):
        monkeypatch.setenv("SQLITE_DB_PATH", str(price_db_path))

        engine = SQLiteDataEngine()

        assert engine.db_path == price_db_path

    def test_get_sqlite_db_path_raises_when_unconfigured(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SQLITE_DB_PATH", raising=False)

        with pytest.raises(EnvironmentError, match="SQLITE_DB_PATH must be set"):
            get_sqlite_db_path(tmp_path / "missing.env")
