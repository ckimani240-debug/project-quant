"""Public Binance market-data client.

Only public market data is accessed.
No account connection, API key, or trading permissions are used.
"""

import math

import pandas as pd
import requests

from config.settings import load_settings


class BinancePublicDataClient:
    """Retrieve public prices and historical candles from Binance."""

    BASE_URL = "https://api.binance.com"

    CANDLE_COLUMNS = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
        "ignore",
    ]

    def __init__(self, timeout: int = 10) -> None:
        if timeout <= 0:
            raise ValueError("Timeout must be positive")

        self.settings = load_settings()
        self.timeout = timeout
        self.session = requests.Session()

    def _validate_symbol(self, symbol: str) -> str:
        if symbol not in self.settings.symbols:
            raise ValueError(f"Unsupported symbol: {symbol}")

        return symbol.replace("/", "")

    def get_current_price(self, symbol: str) -> float:
        """Get the latest public price for a supported symbol."""

        exchange_symbol = self._validate_symbol(symbol)

        response = self.session.get(
            f"{self.BASE_URL}/api/v3/ticker/price",
            params={"symbol": exchange_symbol},
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()
        price = float(data["price"])

        if not math.isfinite(price) or price <= 0:
            raise ValueError("Exchange returned an invalid market price")

        return price

    def get_current_prices(self) -> dict[str, float]:
        """Get current prices for all configured symbols."""

        return {
            symbol: self.get_current_price(symbol)
            for symbol in self.settings.symbols
        }

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        *,
        closed_only: bool = False,
    ) -> pd.DataFrame:
        """Retrieve historical OHLCV candles for a supported symbol."""

        exchange_symbol = self._validate_symbol(symbol)

        if interval not in self.settings.timeframes:
            raise ValueError(f"Unsupported timeframe: {interval}")

        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("Limit must be an integer")

        if not 1 <= limit <= 1000:
            raise ValueError("Limit must be between 1 and 1000")

        response = self.session.get(
            f"{self.BASE_URL}/api/v3/klines",
            params={
                "symbol": exchange_symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()

        if not data:
            raise ValueError("Exchange returned no candle data")

        frame = pd.DataFrame(data, columns=self.CANDLE_COLUMNS)

        numeric_columns = [
            "open", "high", "low", "close", "volume",
            "quote_volume", "taker_buy_base_volume",
            "taker_buy_quote_volume",
        ]

        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="raise")

        frame["open_time"] = pd.to_datetime(
            frame["open_time"], unit="ms", utc=True
        )
        frame["close_time"] = pd.to_datetime(
            frame["close_time"], unit="ms", utc=True
        )
        frame["trade_count"] = pd.to_numeric(
            frame["trade_count"], errors="raise"
        ).astype("int64")

        if closed_only:
            now = pd.Timestamp.now(tz="UTC")
            frame = frame.loc[
                frame["close_time"] < now
            ].copy()

        return frame
