import pandas as pd
import pytest

from analysis.indicators import calculate_sma


def test_sma_calculates_correct_average():
    prices = pd.Series([10, 20, 30, 40, 50])

    result = calculate_sma(prices, window=3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 20
    assert result.iloc[3] == 30
    assert result.iloc[4] == 40


def test_sma_returns_missing_values_until_window_is_ready():
    prices = pd.Series([10, 20])

    result = calculate_sma(prices, window=3)

    assert result.isna().all()


def test_sma_rejects_zero_window():
    prices = pd.Series([10, 20, 30])

    with pytest.raises(ValueError):
        calculate_sma(prices, window=0)


def test_sma_rejects_negative_window():
    prices = pd.Series([10, 20, 30])

    with pytest.raises(ValueError):
        calculate_sma(prices, window=-2)


def test_sma_rejects_non_integer_window():
    prices = pd.Series([10, 20, 30])

    with pytest.raises(ValueError):
        calculate_sma(prices, window=2.5)


def test_sma_rejects_boolean_window():
    prices = pd.Series([10, 20, 30])

    with pytest.raises(ValueError):
        calculate_sma(prices, window=True)


def test_sma_rejects_non_series_input():
    with pytest.raises(TypeError):
        calculate_sma([10, 20, 30], window=2)
