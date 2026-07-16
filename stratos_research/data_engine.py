from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
from typing import Iterable

import pandas as pd


PRICE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
SQLITE_DB_PATH_ENV_VAR = "SQLITE_DB_PATH"


@dataclass(frozen=True)
class InMemorySource:
    """Small in-memory market data source for prepared OHLCV bars."""

    data: pd.DataFrame

    def to_dataframe(self) -> pd.DataFrame:
        """Return a defensive copy of the source data."""
        return self.data.copy()


class SQLiteDataEngine:
    """Load daily OHLCV bars from the local SQLite price history database."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_sqlite_db_path()

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "SQLiteDataEngine":
        """Create an engine using the SQLite database path from the environment."""
        return cls(get_sqlite_db_path(env_path))

    def load_daily_prices(
        self,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
    ) -> pd.DataFrame:
        """Load PyBroker-shaped daily price bars for the requested tickers."""
        ticker_list = self._normalise_tickers(tickers)
        start_date = self._normalise_date(start, "start")
        end_date = self._normalise_date(end, "end")

        if end_date < start_date:
            raise ValueError(f"end ({end_date}) must be on or after start ({start_date})")

        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.db_path}")

        placeholders = ", ".join("?" for _ in ticker_list)
        query = f"""
            SELECT
                COALESCE(ph.symbol, s.ticker) AS symbol,
                ph.date,
                ph.open,
                ph.high,
                ph.low,
                ph.close,
                ph.volume
            FROM price_history AS ph
            LEFT JOIN securities AS s ON s.id = ph.security_id
            WHERE (ph.symbol IN ({placeholders}) OR s.ticker IN ({placeholders}))
              AND ph.date BETWEEN ? AND ?
            ORDER BY ph.date ASC, symbol ASC
        """
        params = [*ticker_list, *ticker_list, start_date, end_date]

        with sqlite3.connect(self.db_path) as connection:
            frame = pd.read_sql_query(query, connection, params=params)

        return self._format_price_frame(frame)

    def load_aligned_daily_prices(
        self,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
    ) -> pd.DataFrame:
        """Load daily bars and align all tickers to a shared daily calendar."""
        ticker_list = self._normalise_tickers(tickers)
        start_date = self._normalise_date(start, "start")
        end_date = self._normalise_date(end, "end")
        prices = self.load_daily_prices(ticker_list, start_date, end_date)

        return self.align_daily_prices(prices, ticker_list, start_date, end_date)

    def create_in_memory_source(
        self,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
        align_timelines: bool = True,
    ) -> InMemorySource:
        """Create an in-memory source from SQLite-backed daily price bars."""
        if align_timelines:
            data = self.load_aligned_daily_prices(tickers, start, end)
        else:
            data = self.load_daily_prices(tickers, start, end)

        return InMemorySource(data)

    def loadDailyPrices(
        self,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
    ) -> pd.DataFrame:
        """Compatibility alias for the UML class spec."""
        return self.load_daily_prices(tickers, start, end)

    def createInMemorySource(
        self,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
        align_timelines: bool = True,
    ) -> InMemorySource:
        """Compatibility alias for the UML class spec."""
        return self.create_in_memory_source(tickers, start, end, align_timelines)

    @classmethod
    def align_daily_prices(
        cls,
        prices: pd.DataFrame,
        tickers: Iterable[str],
        start: str | date,
        end: str | date,
    ) -> pd.DataFrame:
        """Synchronize mixed asset calendars onto one gap-free daily timeline."""
        ticker_list = cls._normalise_tickers(tickers)
        start_date = cls._normalise_date(start, "start")
        end_date = cls._normalise_date(end, "end")

        if end_date < start_date:
            raise ValueError(f"end ({end_date}) must be on or after start ({start_date})")

        expected_columns = set(PRICE_COLUMNS)
        missing_columns = expected_columns - set(prices.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"prices missing required columns: {missing}")

        formatted = cls._format_price_frame(prices)
        if formatted.empty:
            return formatted

        requested = formatted[formatted["symbol"].isin(ticker_list)].copy()
        if requested.empty:
            return cls._format_price_frame(requested)

        calendar = pd.date_range(start=start_date, end=end_date, freq="D")
        aligned_frames = []

        for ticker in ticker_list:
            ticker_prices = requested[requested["symbol"] == ticker].sort_values("date")
            if ticker_prices.empty:
                continue

            indexed = ticker_prices.set_index("date").reindex(calendar)
            indexed[["open", "high", "low", "close"]] = indexed[
                ["open", "high", "low", "close"]
            ].ffill()
            indexed["volume"] = indexed["volume"].fillna(0.0)
            indexed["symbol"] = ticker
            indexed = indexed.dropna(subset=["close"])
            indexed.index.name = "date"
            aligned_frames.append(indexed.reset_index())

        if not aligned_frames:
            return cls._format_price_frame(requested.iloc[0:0])

        aligned = pd.concat(aligned_frames, ignore_index=True)
        complete_dates = aligned.groupby("date")["symbol"].nunique()
        complete_dates = complete_dates[complete_dates == len(ticker_list)].index
        aligned = aligned[aligned["date"].isin(complete_dates)]
        aligned = aligned.sort_values(["date", "symbol"], ignore_index=True)

        return cls._format_price_frame(aligned)

    @staticmethod
    def _normalise_tickers(tickers: Iterable[str]) -> list[str]:
        ticker_list = list(tickers)
        if not ticker_list:
            raise ValueError("tickers must not be empty")
        if any(not ticker for ticker in ticker_list):
            raise ValueError("tickers must contain non-empty symbols")
        return ticker_list

    @staticmethod
    def _normalise_date(value: str | date, field_name: str) -> str:
        if isinstance(value, date):
            return value.isoformat()

        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 date") from exc

    @staticmethod
    def _format_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(
                {
                    "symbol": pd.Series(dtype="string"),
                    "date": pd.Series(dtype="datetime64[ns]"),
                    "open": pd.Series(dtype="float64"),
                    "high": pd.Series(dtype="float64"),
                    "low": pd.Series(dtype="float64"),
                    "close": pd.Series(dtype="float64"),
                    "volume": pd.Series(dtype="float64"),
                },
                columns=PRICE_COLUMNS,
            )

        formatted = frame.loc[:, PRICE_COLUMNS].copy()
        formatted["symbol"] = formatted["symbol"].astype("string")
        formatted["date"] = pd.to_datetime(formatted["date"])

        for column in ["open", "high", "low", "close", "volume"]:
            formatted[column] = pd.to_numeric(
                formatted[column],
                errors="coerce",
            ).astype("float64")

        return formatted


def load_env_file(env_path: str | Path = ".env", override: bool = False) -> None:
    """Load simple KEY=VALUE pairs from a local .env file into os.environ."""
    path = Path(env_path)
    if not path.exists():
        return

    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")

        if key.startswith("export "):
            key = key.removeprefix("export ").strip()

        if override or key not in os.environ:
            os.environ[key] = value


def get_sqlite_db_path(env_path: str | Path = ".env") -> Path:
    """Return the configured SQLite database path from SQLITE_DB_PATH."""
    load_env_file(env_path)
    db_path = os.environ.get(SQLITE_DB_PATH_ENV_VAR)

    if not db_path:
        raise EnvironmentError(
            f"{SQLITE_DB_PATH_ENV_VAR} must be set in the environment or {env_path}"
        )

    return Path(db_path)
