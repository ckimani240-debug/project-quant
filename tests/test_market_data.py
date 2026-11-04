import pytest
import pandas as pd
from unittest.mock import Mock

from market_data.binance_client import BinancePublicDataClient


@pytest.fixture
def client():
    return BinancePublicDataClient()


def make_response(data):
    response = Mock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


def test_current_btc_price(client):
    client.session.get = Mock(
        return_value=make_response({"symbol": "BTCUSDT", "price": "60000.50"})
    )

    price = client.get_current_price("BTC/USDT")

    assert price == 60000.50
    client.session.get.assert_called_once()


def test_current_eth_price(client):
    client.session.get = Mock(
        return_value=make_response({"symbol": "ETHUSDT", "price": "2000"})
    )

    assert client.get_current_price("ETH/USDT") == 2000.0


def test_unsupported_symbol_is_rejected(client):
    with pytest.raises(ValueError, match="Unsupported symbol"):
        client.get_current_price("DOGE/USDT")


@pytest.mark.parametrize("price", ["0", "-1", "nan", "inf"])
def test_invalid_current_price_is_rejected(client, price):
    client.session.get = Mock(
        return_value=make_response({"price": price})
    )

    with pytest.raises(ValueError, match="invalid market price"):
        client.get_current_price("BTC/USDT")


def test_invalid_timeframe_is_rejected(client):
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        client.get_historical_candles("BTC/USDT", "3m")


@pytest.mark.parametrize("limit", [0, 1001, -1, 1.5, True])
def test_invalid_candle_limit_is_rejected(client, limit):
    with pytest.raises(ValueError):
        client.get_historical_candles("BTC/USDT", "1h", limit)


def test_historical_candles_are_converted_to_dataframe(client):
    candle = [
        1790000000000,
        "60000",
        "61000",
        "59000",
        "60500",
        "12.5",
        1790003599999,
        "750000",
        120,
        "6.5",
        "390000",
        "0",
    ]

    client.session.get = Mock(
        return_value=make_response([candle])
    )

    result = client.get_historical_candles(
        "BTC/USDT", "1h", limit=1
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["close"] == 60500.0
    assert result.iloc[0]["volume"] == 12.5
    assert result.iloc[0]["trade_count"] == 120
    assert result.iloc[0]["open_time"].tz is not None


def test_empty_candle_response_is_rejected(client):
    client.session.get = Mock(
        return_value=make_response([])
    )

    with pytest.raises(ValueError, match="no candle data"):
        client.get_historical_candles("BTC/USDT", "1h")
